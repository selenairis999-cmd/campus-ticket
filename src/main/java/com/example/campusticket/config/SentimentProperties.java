package com.example.campusticket.config;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

/**
 * 评论情感分析相关配置（对应 application.yml 的 sentiment: 块）。
 * Python 解释器与脚本路径均走配置，避免代码硬编码，便于迁移部署。
 */
@Component
@ConfigurationProperties(prefix = "sentiment")
public class SentimentProperties {

    /** Python 解释器路径（默认使用系统 PATH 中的 python） */
    private String pythonPath = "python";

    /** 增量情感分析脚本（predict_new.py）绝对路径 */
    private String predictScript = "predict_new.py";

    /**
     * 模型指标脚本（model_metrics.py）路径。
     * 仅供人工/命令行复现论文 6.4 节实验使用；管理端的模型指标卡片固定读取
     * sentiment/experiments/metrics.json，不调用本脚本。
     */
    private String metricsScript = "model_metrics.py";

    public String getPythonPath() { return pythonPath; }
    public void setPythonPath(String pythonPath) { this.pythonPath = pythonPath; }
    public String getPredictScript() { return predictScript; }
    public void setPredictScript(String predictScript) { this.predictScript = predictScript; }
    public String getMetricsScript() { return metricsScript; }
    public void setMetricsScript(String metricsScript) { this.metricsScript = metricsScript; }
}
