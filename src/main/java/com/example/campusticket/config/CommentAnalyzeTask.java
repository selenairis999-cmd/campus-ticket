package com.example.campusticket.config;

import com.example.campusticket.common.ScriptPathResolver;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import java.io.File;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.TimeUnit;

/**
 * 评论情感分析定时任务
 * 每 60 秒自动调用一次 Python 增量分析脚本（predict_new.py），
 * 自动把"待分析"（sentiment 为 NULL）的评论预测回填。
 * 同时暴露 analyzeNow() 供管理端"立即分析"按钮手动触发。
 */
@Slf4j
@Component
public class CommentAnalyzeTask {

    @Autowired
    private SentimentProperties sentimentProperties;

    @Scheduled(fixedDelay = 60_000)   // 上次执行结束后 60 秒再跑一次
    public void scheduledAnalyze() {
        String result = analyzeNow();
        if (result != null) {
            log.info("[情感分析定时任务] 执行完成：\n{}", result);
        }
    }

    /** 立即执行一次增量分析，返回脚本输出；失败或无输出返回 null */
    public String analyzeNow() {
        try {
            // 输出重定向到临时文件再等待：避免脚本挂起时 readAllBytes 无限阻塞调度线程
            File outputFile = File.createTempFile("sentiment_", ".log");
            outputFile.deleteOnExit();
            File script = ScriptPathResolver.resolve(sentimentProperties.getPredictScript());
            if (!script.isFile()) {
                log.warn("[情感分析] 脚本不存在，已跳过：{}（请检查 sentiment.predict-script 配置）",
                        script.getAbsolutePath());
                return null;
            }
            ProcessBuilder pb = new ProcessBuilder(
                    sentimentProperties.getPythonPath(),
                    script.getAbsolutePath());
            pb.redirectErrorStream(true);
            pb.redirectOutput(outputFile);
            // 强制 Python 子进程以 UTF-8 输出，避免 Windows 默认 GBK 导致中文乱码
            pb.environment().put("PYTHONIOENCODING", "utf-8");
            Process process = pb.start();
            boolean finished = process.waitFor(60, TimeUnit.SECONDS);
            if (!finished) {
                process.destroyForcibly();
                log.warn("[情感分析] 执行超时（>60s），已强制终止");
                return null;
            }
            String output = new String(java.nio.file.Files.readAllBytes(outputFile.toPath()), StandardCharsets.UTF_8);
            outputFile.delete();
            if (finished && process.exitValue() == 0) {
                return output.trim();
            }
            log.warn("[情感分析] 执行异常（finished={}, exit={}）：\n{}",
                    finished, process.exitValue(), output.trim());
            return null;
        } catch (Exception e) {
            log.error("[情感分析] 调用 Python 失败", e);
            return null;
        }
    }
}
