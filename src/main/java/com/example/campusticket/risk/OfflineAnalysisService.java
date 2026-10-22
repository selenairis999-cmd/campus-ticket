package com.example.campusticket.risk;

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.example.campusticket.common.ScriptPathResolver;
import com.example.campusticket.entity.Activity;
import com.example.campusticket.entity.GrabLog;
import com.example.campusticket.mapper.ActivityMapper;
import com.example.campusticket.mapper.GrabLogMapper;
import com.example.campusticket.vo.OfflineAnalysisResultVO;
import com.example.campusticket.vo.OfflineAnomalyVO;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Comparator;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.TimeUnit;

/**
 * 离线检测调度服务：管理端"运行离线检测"按钮的后端实现
 * 按活动串行调用 risk-analysis 下三段 Python 脚本（导出 → 特征工程 → 孤立森林），
 * 完成后解析 anomaly_report.csv 返回结构化结果。
 * 定位：安全运营侧工具链，人工触发 + 人工研判，不做定时自动化。
 */
@Slf4j
@Service
public class OfflineAnalysisService {

    /** 流水线脚本（按序执行，脚本以相对路径读写 output/） */
    private static final String[] PIPELINE = {
            "export_grab_log.py", "feature_engineering.py", "isolation_forest.py"
    };

    private static final long STEP_TIMEOUT_SECONDS = 90;

    @Autowired
    private RiskProperties properties;

    @Autowired
    private GrabLogMapper grabLogMapper;

    @Autowired
    private ActivityMapper activityMapper;

    /** 可分析的活动：有抢票日志的活动 + 日志量（下拉框数据源） */
    public List<Map<String, Object>> analyzableActivities() {
        List<Map<String, Object>> grouped = grabLogMapper.selectMaps(
                new QueryWrapper<GrabLog>()
                        .select("activity_id AS activityId", "COUNT(*) AS logCount")
                        .isNotNull("activity_id")
                        .groupBy("activity_id")
                        .orderByDesc("logCount"));
        if (grouped.isEmpty()) {
            return new ArrayList<>();
        }
        List<Long> ids = grouped.stream()
                .map(m -> ((Number) m.get("activityId")).longValue())
                .toList();
        Map<Long, Activity> actMap = activityMapper.selectBatchIds(ids).stream()
                .collect(HashMap::new, (m, a) -> m.put(a.getId(), a), HashMap::putAll);
        List<Map<String, Object>> result = new ArrayList<>();
        for (Map<String, Object> g : grouped) {
            long activityId = ((Number) g.get("activityId")).longValue();
            Map<String, Object> row = new LinkedHashMap<>();
            row.put("activityId", activityId);
            row.put("logCount", ((Number) g.get("logCount")).longValue());
            Activity a = actMap.get(activityId);
            row.put("title", a != null ? a.getTitle() : "未知活动");
            result.add(row);
        }
        return result;
    }

    /** 运行离线检测：activityId 传给第 1 步导出脚本，串跑三步后解析报告 */
    public OfflineAnalysisResultVO run(Long activityId) {
        File dir = ScriptPathResolver.resolve(properties.getAnalysisDir());
        if (!dir.isDirectory()) {
            throw new IllegalStateException("离线检测脚本目录不存在：" + dir.getAbsolutePath());
        }
        StringBuilder console = new StringBuilder();
        String[] args = activityId == null ? new String[0] : new String[]{String.valueOf(activityId)};
        for (String script : PIPELINE) {
            String out = exec(script, args, dir);
            console.append("===== ").append(script).append(" =====\n").append(out.trim()).append("\n\n");
        }
        List<OfflineAnomalyVO> rows = parseReport(new File(dir, "output" + File.separator + "anomaly_report.csv"));
        rows.sort(Comparator.comparingDouble(OfflineAnomalyVO::getIfScore));

        OfflineAnalysisResultVO vo = new OfflineAnalysisResultVO();
        vo.setActivityId(activityId);
        vo.setRows(rows);
        vo.setAnalyzedUsers(rows.size());
        vo.setAnomalyCount((int) rows.stream().filter(OfflineAnomalyVO::isIfAnomaly).count());
        String c = console.toString();
        vo.setConsole(c.length() > 6000 ? "…（前段截断）\n" + c.substring(c.length() - 6000) : c);
        log.info("离线检测完成: activityId={}, users={}, anomaly={}", activityId, rows.size(), vo.getAnomalyCount());
        return vo;
    }

    /** 执行单个脚本：工作目录=脚本目录（脚本用相对路径读写 output/），输出重定向到文件避免流读取死锁 */
    private String exec(String script, String[] args, File dir) {
        List<String> cmd = new ArrayList<>();
        cmd.add(properties.getPythonPath());
        // 脚本名是相对分析目录的裸文件名，这里补成绝对路径：
        // 进程工作目录已设为 dir，但显式绝对路径可避免不同 JVM/平台下的相对路径歧义
        cmd.add(new File(dir, script).getAbsolutePath());
        cmd.addAll(Arrays.asList(args));
        File consoleFile = new File(dir, "output" + File.separator + "_step_console.txt");
        try {
            ProcessBuilder pb = new ProcessBuilder(cmd);
            pb.directory(dir);
            pb.redirectErrorStream(true);
            pb.redirectOutput(consoleFile);
            pb.environment().put("PYTHONIOENCODING", "utf-8");
            Process process = pb.start();
            boolean finished = process.waitFor(STEP_TIMEOUT_SECONDS, TimeUnit.SECONDS);
            if (!finished) {
                process.destroyForcibly();
                throw new IllegalStateException(script + " 执行超时（>" + STEP_TIMEOUT_SECONDS + "s）");
            }
            String output = readAll(consoleFile);
            if (process.exitValue() != 0) {
                throw new IllegalStateException(script + " 执行失败（exit=" + process.exitValue() + "）：\n" + output);
            }
            return output;
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException(script + " 被中断", e);
        } catch (IOException e) {
            throw new IllegalStateException("调用 Python 失败（请检查 risk.python-path 配置）：" + e.getMessage(), e);
        }
    }

    private String readAll(File file) throws IOException {
        StringBuilder sb = new StringBuilder();
        try (BufferedReader reader = new BufferedReader(
                new InputStreamReader(new FileInputStream(file), StandardCharsets.UTF_8))) {
            String line;
            while ((line = reader.readLine()) != null) {
                sb.append(line).append('\n');
            }
        }
        return sb.toString();
    }

    /** 解析 anomaly_report.csv（utf-8-sig；末列说明文本可能含引号/分号，用带引号状态机的 CSV 解析） */
    private List<OfflineAnomalyVO> parseReport(File csv) {
        if (!csv.isFile()) {
            throw new IllegalStateException("未生成检测报告：" + csv.getAbsolutePath());
        }
        List<OfflineAnomalyVO> rows = new ArrayList<>();
        try (BufferedReader reader = new BufferedReader(
                new InputStreamReader(new FileInputStream(csv), StandardCharsets.UTF_8))) {
            String headerLine = reader.readLine();
            if (headerLine == null) {
                throw new IllegalStateException("检测报告为空");
            }
            List<String> header = parseCsvLine(headerLine.replace("\uFEFF", ""));
            String line;
            while ((line = reader.readLine()) != null) {
                if (line.isBlank()) {
                    continue;
                }
                List<String> f = parseCsvLine(line);
                OfflineAnomalyVO vo = new OfflineAnomalyVO();
                vo.setUsername(field(f, header, "username"));
                vo.setIfScore(Double.parseDouble(field(f, header, "if_score")));
                vo.setIfAnomaly(Boolean.parseBoolean(field(f, header, "if_anomaly")));
                vo.setSigAnomaly(Boolean.parseBoolean(field(f, header, "sig_anomaly")));
                vo.setReqCount((int) Double.parseDouble(field(f, header, "req_count")));
                vo.setIntervalMean(Double.parseDouble(field(f, header, "interval_mean")));
                vo.setIntervalMin(Double.parseDouble(field(f, header, "interval_min")));
                vo.setConflictRate(Double.parseDouble(field(f, header, "conflict_rate")));
                vo.setTop3Features(field(f, header, "top3_features"));
                rows.add(vo);
            }
        } catch (IOException e) {
            throw new IllegalStateException("读取检测报告失败：" + e.getMessage(), e);
        }
        return rows;
    }

    private String field(List<String> values, List<String> header, String name) {
        int idx = header.indexOf(name);
        return idx >= 0 && idx < values.size() ? values.get(idx).trim() : "";
    }

    /** 单行 CSV 解析：处理双引号包裹、引号转义与逗号分隔 */
    private List<String> parseCsvLine(String line) {
        List<String> out = new ArrayList<>();
        StringBuilder cur = new StringBuilder();
        boolean inQuotes = false;
        for (int i = 0; i < line.length(); i++) {
            char c = line.charAt(i);
            if (inQuotes) {
                if (c == '"') {
                    if (i + 1 < line.length() && line.charAt(i + 1) == '"') {
                        cur.append('"');
                        i++;
                    } else {
                        inQuotes = false;
                    }
                } else {
                    cur.append(c);
                }
            } else if (c == '"') {
                inQuotes = true;
            } else if (c == ',') {
                out.add(cur.toString());
                cur.setLength(0);
            } else {
                cur.append(c);
            }
        }
        out.add(cur.toString());
        return out;
    }
}
