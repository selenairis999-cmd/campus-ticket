package com.example.campusticket.common;

import cn.hutool.crypto.SecureUtil;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * 动态二维码单元测试（覆盖签名格式与核销时间窗）
 * 重点覆盖时间窗方向性：过期码与"未来时间戳"伪造码都必须被拒绝。
 */
class QrCodeUtilTest {

    private static final String SECRET = "unit-test-secret";

    private QrCodeUtil qrCodeUtil;

    @BeforeEach
    void setUp() {
        qrCodeUtil = new QrCodeUtil();
        ReflectionTestUtils.setField(qrCodeUtil, "secret", SECRET);
    }

    /** 按被测类的算法手工签发一个指定时间戳的码，用于构造各种时间窗场景 */
    private String signAt(String ticketCode, long ts) {
        String sign = SecureUtil.sha256(ticketCode + "&" + ts + "&" + SECRET);
        return ticketCode + "." + ts + "." + sign;
    }

    @Test
    @DisplayName("正常码：生成后立即校验应通过并返回票号")
    void buildThenVerifyShouldPass() {
        String qrContent = qrCodeUtil.build("T20261013001");
        assertEquals("T20261013001", qrCodeUtil.verify(qrContent));
    }

    @Test
    @DisplayName("内容为空应被拒绝")
    void nullContentShouldFail() {
        RuntimeException e = assertThrows(RuntimeException.class, () -> qrCodeUtil.verify(null));
        assertEquals("二维码内容为空", e.getMessage());
    }

    @Test
    @DisplayName("静态票号（无时间戳无签名）应被拒绝，防止旧静态码继续可用")
    void staticTicketCodeShouldFail() {
        RuntimeException e = assertThrows(RuntimeException.class, () -> qrCodeUtil.verify("T20261013001"));
        assertEquals("二维码格式错误，请使用动态二维码", e.getMessage());
    }

    @Test
    @DisplayName("时间戳非数字应被拒绝")
    void nonNumericTimestampShouldFail() {
        RuntimeException e = assertThrows(RuntimeException.class,
                () -> qrCodeUtil.verify("T20261013001.abc.deadbeef"));
        assertEquals("二维码内容非法", e.getMessage());
    }

    @Test
    @DisplayName("签名被篡改应被拒绝")
    void tamperedSignatureShouldFail() {
        String qrContent = qrCodeUtil.build("T20261013001");
        String tampered = qrContent.substring(0, qrContent.length() - 1) + "0";
        RuntimeException e = assertThrows(RuntimeException.class, () -> qrCodeUtil.verify(tampered));
        assertEquals("二维码签名校验失败", e.getMessage());
    }

    @Test
    @DisplayName("换了密钥签发的码应被拒绝（密钥只在服务端）")
    void forgedWithWrongSecretShouldFail() {
        String forged = "T20261013001." + System.currentTimeMillis()
                + "." + SecureUtil.sha256("T20261013001&" + System.currentTimeMillis() + "&other-secret");
        assertThrows(RuntimeException.class, () -> qrCodeUtil.verify(forged));
    }

    @Test
    @DisplayName("过期码（超出有效期+容差）应被拒绝")
    void expiredCodeShouldFail() {
        long tooOld = System.currentTimeMillis() - QrCodeUtil.VALID_MILLIS - QrCodeUtil.CLOCK_TOLERANCE_MILLIS - 1000;
        RuntimeException e = assertThrows(RuntimeException.class,
                () -> qrCodeUtil.verify(signAt("T20261013001", tooOld)));
        assertEquals("二维码已过期，请刷新后重试", e.getMessage());
    }

    /**
     * 回归测试：修复前的实现只判断 now - ts > VALID_MILLIS（单向），
     * 攻击者若拿到密钥即可签发一个时间戳在未来的码，使其长期有效。
     */
    @Test
    @DisplayName("未来时间戳的伪造码应被拒绝（单向时间窗漏洞回归测试）")
    void futureTimestampShouldFail() {
        long oneHourLater = System.currentTimeMillis() + 60 * 60 * 1000L;
        RuntimeException e = assertThrows(RuntimeException.class,
                () -> qrCodeUtil.verify(signAt("T20261013001", oneHourLater)));
        assertEquals("二维码已过期，请刷新后重试", e.getMessage());
    }

    @Test
    @DisplayName("略超容差的未来码应被拒绝，容差之内的时钟偏差应放行")
    void clockToleranceBoundary() {
        long now = System.currentTimeMillis();
        long beyond = now + QrCodeUtil.VALID_MILLIS + QrCodeUtil.CLOCK_TOLERANCE_MILLIS + 1000;
        assertThrows(RuntimeException.class, () -> qrCodeUtil.verify(signAt("T20261013001", beyond)));

        // 容差范围内（例如客户端时钟快 1.5 秒）仍应通过
        long withinTolerance = now + QrCodeUtil.VALID_MILLIS + QrCodeUtil.CLOCK_TOLERANCE_MILLIS - 1500;
        assertEquals("T20261013001", qrCodeUtil.verify(signAt("T20261013001", withinTolerance)));
    }

    @Test
    @DisplayName("同一票号每次生成的签名内容不同（含毫秒时间戳）")
    void buildShouldEmbedTimestamp() {
        String qrContent = qrCodeUtil.build("T20261013001");
        String[] parts = qrContent.split("\\.");
        assertEquals(3, parts.length);
        long ts = Long.parseLong(parts[1]);
        assertTrue(Math.abs(System.currentTimeMillis() - ts) < 5000);
    }
}
