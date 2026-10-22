package com.example.campusticket.common;

import java.io.File;
import java.net.URI;

/**
 * Python 脚本路径解析工具。
 *
 * <p>配置文件中脚本路径写的是相对项目根目录的相对路径（如 {@code sentiment/predict_new.py}），
 * 这样项目拷到任何机器、任何目录都能直接跑。但相对路径是相对 JVM 的工作目录解析的，
 * 若从别的目录启动 jar 就会找不到脚本。本工具按以下顺序解析，兼顾可移植性与健壮性：
 *
 * <ol>
 *   <li>配置为绝对路径 → 原样使用；</li>
 *   <li>相对 {@code user.dir}（即启动时的工作目录，正常从项目根目录启动即命中）；</li>
 *   <li>相对 jar 包所在目录（从 target 目录直接双击 jar 启动时命中）；</li>
 *   <li>都不存在时返回第 2 种结果，由调用方给出清晰的"路径不存在"报错。</li>
 * </ol>
 */
public final class ScriptPathResolver {

    private ScriptPathResolver() {
    }

    /**
     * 解析配置中的脚本/目录路径。
     *
     * @param configured 配置文件里的原始值，可为相对路径或绝对路径
     * @return 解析后的 File；调用方需自行判断是否存在
     */
    public static File resolve(String configured) {
        File path = new File(configured);
        if (path.isAbsolute()) {
            return path;
        }
        File fromWorkDir = new File(System.getProperty("user.dir"), configured);
        if (fromWorkDir.exists()) {
            return fromWorkDir;
        }
        File fromJarDir = new File(jarDirectory(), configured);
        if (fromJarDir.exists()) {
            return fromJarDir;
        }
        return fromWorkDir;
    }

    /** 运行中 class/jar 所在目录；无法确定时退回当前工作目录 */
    private static File jarDirectory() {
        try {
            URI uri = ScriptPathResolver.class.getProtectionDomain()
                    .getCodeSource().getLocation().toURI();
            File self = new File(uri);
            File parent = self.isFile() ? self.getParentFile() : self;
            return parent != null ? parent : new File(System.getProperty("user.dir"));
        } catch (Exception e) {
            return new File(System.getProperty("user.dir"));
        }
    }
}
