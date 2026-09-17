import { AsyncLocalStorage } from 'async_hooks';

/**
 * 租户上下文（请求级）。
 *
 * ★ 为什么用 AsyncLocalStorage 而不是「每个方法手动传 tenantId」
 * 手动传参只要有一处忘记，就是一次跨租户数据泄露（本项目风险清单 R8，定级「极高」）。
 * AsyncLocalStorage 让 tenantId 在整条调用链隐式可用，Prisma 扩展在底层统一注入，
 * 业务代码**根本接触不到** tenantId 参数，从源头消灭漏写。
 *
 * 用法：
 *   TenantContext.run({ tenantId: 1n }, () => { ... })   // 中间件/MQ 消费者里包一层
 *   TenantContext.getTenantId()                          // 业务代码里读取（一般不需要）
 */
export interface TenantContextValue {
  /** 当前租户 ID。平台级操作为 0n。 */
  tenantId: bigint;
  /** 当前登录用户 ID（可空：定时任务、MQ 消费者） */
  userId?: bigint;
  /** 角色：1家长 2教师 3机构管理员 4平台管理员 */
  role?: number;
}

const storage = new AsyncLocalStorage<TenantContextValue>();

export class TenantContext {
  /** 在当前异步上下文内绑定租户信息 */
  static run<T>(value: TenantContextValue, fn: () => T): T {
    return storage.run(value, fn);
  }

  static get(): TenantContextValue | undefined {
    return storage.getStore();
  }

  /**
   * 读取当前租户 ID。
   * @throws 上下文未建立时抛错 —— 这是**故意的**：宁可显式失败，也不要静默查全表。
   */
  static requireTenantId(): bigint {
    const ctx = storage.getStore();
    if (!ctx || ctx.tenantId === undefined) {
      throw new Error(
        '[TenantContext] 当前调用链没有租户上下文。' +
          '请确认请求经过了 TenantMiddleware，或异步任务/定时任务用 TenantContext.run() 包裹。',
      );
    }
    return ctx.tenantId;
  }

  /** 可选读取：返回 undefined 而不抛错，用于「平台级查询」等场景 */
  static getTenantId(): bigint | undefined {
    return storage.getStore()?.tenantId;
  }
}
