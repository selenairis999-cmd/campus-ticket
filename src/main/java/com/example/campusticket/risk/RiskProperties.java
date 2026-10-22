package com.example.campusticket.risk;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

/**
 * 抢票风控阈值配置（对应 application.yml 的 risk: 块）
 */
@Component
@ConfigurationProperties(prefix = "risk")
public class RiskProperties {

    /** 总开关：false 时只记日志不拦截 */
    private boolean enabled = true;

    /** 规则R1：统计窗口（秒） */
    private long userWindowSeconds = 10;

    /** 规则R1：窗口内请求数上限 */
    private int userMaxRequests = 5;

    /** 规则R1：命中后惩罚时长（秒） */
    private long userPunishSeconds = 30;

    /** 规则R2：开关（默认关，防NAT误杀） */
    private boolean ipRuleEnabled = false;

    /** 规则R2：统计窗口（秒） */
    private long ipWindowSeconds = 60;

    /** 规则R2：同IP同活动账号数上限 */
    private int ipMaxAccounts = 3;

    /** 离线检测：Python 解释器路径（默认使用系统 PATH 中的 python，可在 application.yml 中覆盖） */
    private String pythonPath = "python";

    /** 离线检测：脚本目录（脚本以相对路径读写 output/） */
    private String analysisDir = "risk-analysis";

    public boolean isEnabled() { return enabled; }
    public void setEnabled(boolean enabled) { this.enabled = enabled; }
    public long getUserWindowSeconds() { return userWindowSeconds; }
    public void setUserWindowSeconds(long userWindowSeconds) { this.userWindowSeconds = userWindowSeconds; }
    public int getUserMaxRequests() { return userMaxRequests; }
    public void setUserMaxRequests(int userMaxRequests) { this.userMaxRequests = userMaxRequests; }
    public long getUserPunishSeconds() { return userPunishSeconds; }
    public void setUserPunishSeconds(long userPunishSeconds) { this.userPunishSeconds = userPunishSeconds; }
    public boolean isIpRuleEnabled() { return ipRuleEnabled; }
    public void setIpRuleEnabled(boolean ipRuleEnabled) { this.ipRuleEnabled = ipRuleEnabled; }
    public long getIpWindowSeconds() { return ipWindowSeconds; }
    public void setIpWindowSeconds(long ipWindowSeconds) { this.ipWindowSeconds = ipWindowSeconds; }
    public int getIpMaxAccounts() { return ipMaxAccounts; }
    public void setIpMaxAccounts(int ipMaxAccounts) { this.ipMaxAccounts = ipMaxAccounts; }
    public String getPythonPath() { return pythonPath; }
    public void setPythonPath(String pythonPath) { this.pythonPath = pythonPath; }
    public String getAnalysisDir() { return analysisDir; }
    public void setAnalysisDir(String analysisDir) { this.analysisDir = analysisDir; }
}
