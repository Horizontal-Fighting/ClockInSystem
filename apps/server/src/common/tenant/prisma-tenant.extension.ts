import { Prisma } from '@prisma/client';
import { TenantContext } from './tenant-context';

/**
 * ★★★ 多租户自动注入扩展（本项目最重要的 200 行代码）★★★
 *
 * 做什么：在 Prisma 查询层拦截所有对「含 tenantId 字段的模型」的操作，
 *        自动把 tenantId 拼进 where / data，业务代码完全无感。
 *
 * 为什么必须有：docs/02 文档 1.4.2 第 2 条 —— 「ORM 层自动注入，禁止手写」。
 *  手写 tenantId 的失败模式是：新加一个查询时漏写 → A 机构看到 B 机构数据。
 *  这是 SaaS 最致命的事故，且往往在上线数月后才被发现。
 *
 * 三条硬约束（违反会抛错，不会静默放过）：
 *   1. findUnique / findUniqueOrThrow —— **禁用**。它按唯一键查，无法注入 tenantId，
 *      是越权的主要来源。请改用 findFirst（会自动注入）。
 *   2. 任何对租户表的操作都必须有上下文，否则抛错（见 TenantContext.requireTenantId）。
 *   3. create 时若调用方已显式传 tenantId，以**上下文为准**（绝不接受前端传参）。
 */

/** 需要注入的写操作：给 data 加 tenantId */
const WRITE_OPS = new Set(['create', 'createMany', 'upsert']);
/** 需要注入的读/改/删操作：给 where 加 tenantId */
const QUERY_OPS = new Set([
  'findFirst',
  'findFirstOrThrow',
  'findMany',
  'count',
  'aggregate',
  'groupBy',
  'updateMany',
  'deleteMany',
  'update',
  'delete',
]);

/**
 * 从 Prisma 元数据里动态识别「哪些模型有 tenantId」。
 * ★ 用运行时反射而不是硬编码数组：新增业务表时自动生效，不会因为忘记更新列表而漏掉。
 */
function getTenantModelNames(): Set<string> {
  const dmmf = (Prisma as unknown as { dmmf?: { datamodel?: { models?: Array<{ name: string; fields?: Array<{ name: string }> }> } } }).dmmf;
  const models = dmmf?.datamodel?.models ?? [];
  return new Set(
    models
      .filter((m) => (m.fields ?? []).some((f) => f.name === 'tenantId'))
      .map((m) => m.name),
  );
}

export function tenantExtension() {
  const tenantModels = getTenantModelNames();

  return Prisma.defineExtension((prisma) =>
    prisma.$extends({
      name: 'tenant-isolation',
      query: {
        $allModels: {
          async $allOperations({ model, operation, args, query }) {
            // Tenant / User 这类全局表没有 tenantId，直接放行
            if (!tenantModels.has(model)) {
              return query(args as never);
            }

            // 写操作期间的 serializer 等内部操作不注入
            if (operation === 'findUnique' || operation === 'findUniqueOrThrow') {
              throw new Error(
                `[tenant-isolation] 禁止对 ${model} 使用 ${operation}。` +
                  '该方法按唯一键查询，无法自动注入 tenantId，是跨租户越权的主要来源。' +
                  '请改用 findFirst（会自动带上 tenantId）。',
              );
            }

            const tenantId = TenantContext.requireTenantId();

            if (WRITE_OPS.has(operation)) {
              return query(injectIntoData(args, tenantId, operation) as never);
            }

            if (QUERY_OPS.has(operation)) {
              return query(injectIntoWhere(args, tenantId) as never);
            }

            return query(args as never);
          },
        },
      },
    }),
  );
}

/** create / createMany / upsert：把 tenantId 塞进 data */
function injectIntoData(args: unknown, tenantId: bigint, operation: string): unknown {
  const a = (args ?? {}) as Record<string, any>;

  if (operation === 'createMany') {
    const data = Array.isArray(a.data) ? a.data : [a.data];
    return { ...a, data: data.map((d: any) => ({ ...d, tenantId })) };
  }

  if (operation === 'upsert') {
    return {
      ...a,
      where: { ...(a.where ?? {}), tenantId },
      create: { ...(a.create ?? {}), tenantId },
      update: a.update ?? {},
    };
  }

  // create
  return { ...a, data: { ...(a.data ?? {}), tenantId } };
}

/**
 * 把 tenantId 塞进 where。
 * 覆盖：findFirst / findFirstOrThrow / findMany / count / aggregate / groupBy
 *      / updateMany / deleteMany / update / delete
 */
function injectIntoWhere(args: unknown, tenantId: bigint): unknown {
  const a = (args ?? {}) as Record<string, any>;
  const where = a.where;

  // 没有 where 条件 → 直接建一个（例如 findMany() 查全部）
  if (!where) {
    return { ...a, where: { tenantId } };
  }

  // 已有 where 且与 tenantId 冲突 → 以上下文为准，覆盖掉（含前端传参的情况）
  // 注意要用 AND 包一层，避免调用方原本的 OR 条件被 tenantId 覆盖后语义改变
  const { tenantId: _ignored, ...rest } = where;
  return {
    ...a,
    where: Object.keys(rest).length > 0 ? { AND: [rest, { tenantId }] } : { tenantId },
  };
}
