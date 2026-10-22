package com.example.campusticket.common;

/**
 * 业务异常：用于「已经发生过写操作、但后续步骤失败」的业务失败分支，用来触发事务回滚。
 *
 * <p>背景：抢票流程是「先扣票种库存 → 再扣活动总库存 → 生成订单与电子票」两次写操作。
 * 如果第二次写失败时只是 {@code return Result.error(...)}，方法正常返回，
 * {@code @Transactional} 不会回滚，就会出现「票种库存已被扣减、却没有生成订单和电子票」的数据不一致。
 * 因此凡是写操作之后失败的分支，一律抛出本异常，让 Spring 回滚整个事务。</p>
 *
 * <p>注意：写操作之前的前置校验（活动不存在、时间窗不通过、已抢过、票种不存在等）
 * 没有产生任何写操作，仍可直接返回 {@code Result.error}，不需要回滚。</p>
 */
public class BusinessException extends RuntimeException {

    /** 需要写入 grab_log 的结果码（如 STOCK_EMPTY / VERSION_CONFLICT），可为 null 表示不埋点 */
    private final String logResult;

    public BusinessException(String message) {
        this(message, null);
    }

    public BusinessException(String message, String logResult) {
        super(message);
        this.logResult = logResult;
    }

    public String getLogResult() {
        return logResult;
    }
}
