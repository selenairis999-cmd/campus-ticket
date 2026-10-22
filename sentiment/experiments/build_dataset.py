# -*- coding: utf-8 -*-
"""
build_dataset.py —— 构建情感分析实验数据集（可复现、低重复）

论文 6.4 节的数据集由四类情感模板批量生成，目标构成为：
    好评 832 / 差评 522 / 中评 335 / 无意义 139 = 1828 条
另含 25 条手工编写的"真实风格"评论，用于检验模型对模板生成样本之外的泛化能力。

文本生成方式（沿用项目历史造数脚本的思路，但改为槽位组合，降低重复率）：
    - 好评/中评/差评：句子骨架 × 多个槽位词表（时间、活动、评价、结尾）
    - 无意义：键盘乱码、纯数字串、纯标点、灌水短语（程序化生成）

关键设计：同一条文本不会重复出现（去重后 1828 条），
避免训练集/测试集出现近似重复样本导致准确率虚高。

输出：dataset.csv（content,label），固定随机种子 42，可完全重复生成。

用法：
    python build_dataset.py
"""
import csv
import os
import random

# ----------------------------------------------------------------------------
# 目标类别配额（论文 6.4 节数据集构成）
# ----------------------------------------------------------------------------
TARGET = {2: 832, 1: 335, 0: 522, 9: 139}   # 好评 / 中评 / 差评 / 无意义
LABEL_NAME = {0: '差评', 1: '中评', 2: '好评', 9: '无意义'}
SEED = 42

# ----------------------------------------------------------------------------
# 槽位词表
# ----------------------------------------------------------------------------
ACTS = ['校园音乐节', '迎新晚会', '校园歌手大赛', '社团招新夜', '篮球友谊赛', '脱口秀开放麦',
        '校园开放麦', '毕业歌会', '电竞挑战赛', '读书分享会', '摄影展', '志愿活动',
        '英语角', '编程马拉松', '迎新晚会', '校园音乐节', '社团文化节', '运动会开幕式']

TIMES = ['今天', '昨天', '周末', '上周六', '前天', '晚上', '下午', '这次', '第一次来', '第二次来']

# 好评
PRAISE = ['真的很精彩', '气氛特别棒', '内容特别丰富', '组织得特别好', '现场效果拉满',
          '比想象中好太多', '全程都很投入', '看得特别过瘾', '细节做得很到位',
          '工作人员特别热情', '流程安排很顺畅', '舞台效果超出预期', '干货很多',
          '互动环节设计得很好', '灯光音响都很到位', '整体体验非常棒']
PRAISE_ADJ = ['精彩', '棒', '有意思', '好玩', '震撼', '用心', '专业', '热闹', '舒服']
POS_END = ['下次一定还来', '强烈推荐给大家', '期待下一届', '给主办方点赞', '值回票价',
           '不虚此行', '意犹未尽', '希望以后多办几场', '已经安利给室友了', '明年还要来']
POS_SKEL = [
    '{time}参加了{act}，{praise}，{end}',
    '{act}{praise}，{end}',
    '没想到{act}这么{adj}，{praise}，{end}',
    '{praise}，{end}',
    '{time}的{act}办得真不错，{praise}，{end}',
    '本来没抱太大期望，结果{act}{praise}，{end}',
    '{praise}，特别是{act}的现场氛围，{end}',
    '和朋友一起去的{act}，{praise}，{end}',
]

# 中评
NEU_POINT = ['整体还行', '中规中矩', '没什么特别的感觉', '不好不坏', '普普通通',
             '有几段不错', '凑合能看', '谈不上惊喜', '还算可以', '一般般吧',
             '看个人喜好', '没有想象中那么好']
NEU_END = ['就这样吧', '不功不过', '希望下次能更好', '但也说不上差', '没什么好吐槽的',
           '算是打发时间了', '下次看情况吧', '总体能接受', '期待值别太高就行']
NEU_SKEL = [
    '{time}的{act}，{point}，{end}',
    '{act}{point}，{end}',
    '{point}，{end}',
    '说实话{act}{point}，{end}',
    '陪朋友去的{act}，{point}，{end}',
    '{act}的{aspect}{point}，{end}',
    '{point}，不过{aspect}还可以，{end}',
]
NEU_ASPECT = ['音响', '场地', '流程', '节目', '内容', '组织', '时间安排', '座位']

# 差评
BLAME = ['体验很差', '太失望了', '浪费时间', '组织得一塌糊涂', '完全不符合宣传',
         '现场管理很乱', '音响效果太差', '等待时间太长', '内容太水了', '一点也不值',
         '感觉被坑了', '实在看不下去了', '全程都在煎熬', '再也不会来了']
NEG_END = ['下次不来了', '不推荐', '希望主办方反思', '差评', '后悔来了',
           '建议大家别去', '白跑一趟', '心累', '无语了', '就当交学费了']
NEG_SKEL = [
    '{time}的{act}{blame}，{end}',
    '{act}{blame}，{end}',
    '{blame}，{end}',
    '冲着{act}去的，结果{blame}，{end}',
    '说句实话，{act}{blame}，{end}',
    '{blame}，尤其是{aspect}，{end}',
    '{act}的{aspect}{blame}，{end}',
    '和朋友一起去的，结果{blame}，{end}',
]

# 无意义：灌水短语池（含中文，属于"有效文本但无信息量"）
SPAM = ['到此一游', '打卡', '路过', '凑个字数', '随便看看', '占个楼', '回复一下',
        '我来了我来了', '不知道说啥随便打几个字', '先占个位置', '看看再说', 'emmm',
        '哈哈哈哈', '嘿嘿嘿', '嗯嗯嗯', '来了来了', '留个脚印', '签到',
        '今天天气不错', '作业还没写完就来看这个了', '朋友让我来的', '没什么想说的',
        '好', '不错', '可以', '哦', '知道了', '收到', '沙发', '板凳', '前排',
        '顶一个', '支持一下', '混个脸熟', '潜水多年第一次冒泡']

# 25 条手工真实评论（论文 6.4 节的泛化测试集，必须全部纳入）
MANUAL = [
    ('散场的时候人特别多，挤了半小时才出来，不过整体还是玩得挺开心', 2),
    ('场地布置很漂亮，可惜音响太拉胯了，前几排根本听不清', 1),
    ('真滴不错，爱了爱了，下次还来', 2),
    ('呵呵，下次别叫我了', 0),
    ('还行吧，主要是陪室友来的，自己没什么感觉', 1),
    ('嘉宾讲得挺好，就是时间太长了，后半段我直接睡着了', 1),
    ('签到很快，组织得井井有条，志愿者也很热情', 2),
    ('希望下次时间安排能更合理一点，别让大家饿着肚子等', 0),
    ('说实话期待了很久，结果有点落差，但也不是完全没收获', 1),
    ('救命，这也太好笑了吧，全程没停过', 2),
    ('价格不贵，内容也就那样，一分钱一分货', 1),
    ('怎么会有这么无聊的活动，我居然坚持到了最后', 0),
    ('虽然下雨了，但主办方发了雨衣，细节拉满', 2),
    ('没什么亮点，也没什么槽点，就这样吧', 1),
    ('一进场就后悔了，人挤人，空气都不流通', 0),
    ('小朋友玩得很开心，大人就…你们懂的', 1),
    ('说实话我是被名字骗来的，跟描述完全不符', 0),
    ('氛围感绝了，灯光一打瞬间就有那味了', 2),
    ('第一次参加这种活动，感觉还不错，下次多带几个朋友', 2),
    ('流程有点乱，后半段全靠工作人员吼', 1),
    ('笑死，抽奖环节奖品都没发完就结束了', 0),
    ('干货很多，笔记记了两页纸，值了', 2),
    ('一般般吧，没有宣传的那么好', 1),
    ('别的不说，现场秩序是真的好，很专业', 2),
    ('凑个热闹来的，看完只想说：就这？', 0),
]
MANUAL_SET = {c for c, _ in MANUAL}

PUNCT_POOL = ['！', '！！', '！！！', '。。', '。。。', '。。。。。', '？', '？？',
              '？？？', '？？？？？？', '…', '……', '~~~', '###', '***', '————']

KEYS = 'asdfghjklqwertyuiopzxcvbnm'


def gen_meaningless(rng, need, used):
    """程序化生成无意义样本：键盘乱码 / 纯数字 / 纯标点 / 灌水短语。"""
    out = []
    # 1) 灌水短语（中文但无信息量）
    for s in SPAM:
        if s not in used:
            out.append(s)
            used.add(s)
    # 2) 键盘乱码
    while len(out) < need:
        n = rng.randint(4, 14)
        s = ''.join(rng.choice(KEYS) for _ in range(n))
        if s not in used:
            out.append(s)
            used.add(s)
    # 3) 纯数字串
    while len(out) < need:
        n = rng.randint(4, 11)
        s = ''.join(rng.choice('0123456789') for _ in range(n))
        if s not in used:
            out.append(s)
            used.add(s)
    # 4) 纯标点 / 符号
    while len(out) < need:
        s = rng.choice(PUNCT_POOL)
        if rng.random() < 0.4:
            s = s + rng.choice(PUNCT_POOL)
        if s not in used:
            out.append(s)
            used.add(s)
    # 5) 中文+数字+字母混杂（仿用户乱码输入）
    while len(out) < need:
        parts = []
        for _ in range(rng.randint(2, 4)):
            r = rng.random()
            if r < 0.45:
                parts.append(rng.choice('父母老师朋友同学今天明天昨天然后有的和去来'))
            elif r < 0.75:
                parts.append(str(rng.randint(1, 99)))
            else:
                parts.append(rng.choice('qwertyuiopasdfghjkl'))
        s = ''.join(parts)
        if s not in used and len(s) >= 4:
            out.append(s)
            used.add(s)
    return out[:need]


def gen_sentiment(rng, label, need, used):
    """按类别用槽位骨架生成评论，保证互不重复。"""
    out, tries = [], 0
    while len(out) < need and tries < need * 60:
        tries += 1
        if label == 2:
            s = rng.choice(POS_SKEL).format(
                time=rng.choice(TIMES), act=rng.choice(ACTS), praise=rng.choice(PRAISE),
                adj=rng.choice(PRAISE_ADJ), end=rng.choice(POS_END))
        elif label == 1:
            s = rng.choice(NEU_SKEL).format(
                time=rng.choice(TIMES), act=rng.choice(ACTS), point=rng.choice(NEU_POINT),
                aspect=rng.choice(NEU_ASPECT), end=rng.choice(NEU_END))
        else:
            s = rng.choice(NEG_SKEL).format(
                time=rng.choice(TIMES), act=rng.choice(ACTS), blame=rng.choice(BLAME),
                aspect=rng.choice(NEU_ASPECT), end=rng.choice(NEG_END))
        if rng.random() < 0.25:
            s += rng.choice(['！', '～', '。', '！'])
        if s not in used:
            out.append(s)
            used.add(s)
    return out


def main():
    rng = random.Random(SEED)
    used = set()
    rows = []

    # 手工真实评论优先纳入（必须全部出现）
    for content, lab in MANUAL:
        rows.append((content, lab))
        used.add(content)

    for label in (2, 1, 0):
        need = TARGET[label] - sum(1 for _, l in rows if l == label)
        got = gen_sentiment(rng, label, need, used)
        if len(got) < need:
            raise SystemExit('类别 %s 生成不足：%d/%d' % (LABEL_NAME[label], len(got), need))
        rows.extend((c, label) for c in got)

    need9 = TARGET[9] - sum(1 for _, l in rows if l == 9)
    got9 = gen_meaningless(rng, need9, used)
    if len(got9) < need9:
        raise SystemExit('无意义类生成不足：%d/%d' % (len(got9), need9))
    rows.extend((c, 9) for c in got9)

    rng.shuffle(rows)

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dataset.csv')
    with open(out, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['content', 'label'])
        w.writerows(rows)

    dist = {lab: sum(1 for _, l in rows if l == lab) for lab in (0, 1, 2, 9)}
    uniq = len({c for c, _ in rows})
    print('数据集已生成 ->', out)
    print('样本总数：%d（去重后 %d，重复率 %.1f%%）' % (len(rows), uniq, (1 - uniq / len(rows)) * 100))
    for lab in (0, 1, 2, 9):
        print('  %s(%d) = %d' % (LABEL_NAME[lab], lab, dist[lab]))
    print('手工真实评论纳入：%d/25' % sum(1 for c, _ in rows if c in MANUAL_SET))


if __name__ == '__main__':
    main()
