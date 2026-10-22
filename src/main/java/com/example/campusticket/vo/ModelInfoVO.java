package com.example.campusticket.vo;

import lombok.Data;

@Data
public class ModelInfoVO {
    private String svmAccuracy;        // SVM 测试集准确率
    private String lrAccuracy;         // 逻辑回归测试集准确率
    private String nbAccuracy;         // 朴素贝叶斯测试集准确率
    private String svmRealHitRate;     // SVM 手工评论命中率
    private Integer sampleCount;       // 训练样本数
    private Integer pendingCount;      // 当前待分析评论数
}
