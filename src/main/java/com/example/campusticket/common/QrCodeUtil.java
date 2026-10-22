package com.example.campusticket.common;

import cn.hutool.crypto.SecureUtil;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

/**
 * 动态二维码工具：生成与校验 "票号.时间戳.签名" 三段内容
 * 防截图原理：码内带时间戳，3 秒过期；前端定时刷新，截图转发后扫码必失效
 * 时间窗为双向校验（同时拦截过期码与未来时间戳伪造码），并容忍 ±2s 时钟偏差
 */
@Component
public class QrCodeUtil {

    @Value("${qrcode.secret}")
    private String secret;

    /** 动态码有效期：3 秒（超过即失效，前端需定时刷新） */
    public static final long VALID_MILLIS = 3000;

    /** 允许的客户端/服务器时钟偏差（秒），时间窗为 ±(VALID_MILLIS + TOLERANCE) */
    public static final long CLOCK_TOLERANCE_MILLIS = 2000;

    /** 生成动态二维码内容：票号.时间戳.签名 */
    public String build(String ticketCode) {
        long ts = System.currentTimeMillis();
        String sign = sign(ticketCode, ts);
        return ticketCode + "." + ts + "." + sign;
    }

    /** 校验动态码，成功返回票号；失败抛异常（格式错/签名错/过期） */
    public String verify(String qrContent) {
        if (qrContent == null) {
            throw new RuntimeException("二维码内容为空");
        }
        String[] parts = qrContent.split("\\.");
        if (parts.length != 3) {
            throw new RuntimeException("二维码格式错误，请使用动态二维码");
        }
        String ticketCode = parts[0];
        long ts;
        try {
            ts = Long.parseLong(parts[1]);
        } catch (NumberFormatException e) {
            throw new RuntimeException("二维码内容非法");
        }
        // 1. 签名校验：防止伪造二维码
        if (!sign(ticketCode, ts).equals(parts[2])) {
            throw new RuntimeException("二维码签名校验失败");
        }
        // 2. 时效校验：双向时间窗（同时拦截过期码与未来时间戳的伪造码）
        // 原先只判断 now - ts > VALID_MILLIS（单向），攻击者拿到密钥后可签发一个
        // 时间戳在未来的签名码，使其长期有效；改为绝对值判断后该漏洞被堵住。
        // 额外放宽 CLOCK_TOLERANCE_MILLIS 容忍客户端与服务器的时钟偏差。
        long delta = System.currentTimeMillis() - ts;
        if (Math.abs(delta) > VALID_MILLIS + CLOCK_TOLERANCE_MILLIS) {
            throw new RuntimeException("二维码已过期，请刷新后重试");
        }
        return ticketCode;
    }

    /** SHA256 签名：票号 & 时间戳 & 密钥（密钥只在服务端，前端无法伪造） */
    private String sign(String ticketCode, long ts) {
        return SecureUtil.sha256(ticketCode + "&" + ts + "&" + secret);
    }
}
