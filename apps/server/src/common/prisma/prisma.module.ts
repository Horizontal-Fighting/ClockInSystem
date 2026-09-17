import { Global, Module } from '@nestjs/common';
import { PrismaClient } from '@prisma/client';
import { tenantExtension } from '../tenant/prisma-tenant.extension';

/**
 * 创建「已套上多租户扩展」的 Prisma 客户端。
 *
 * ★ 整个应用**只允许**通过这里拿 Prisma 实例。
 *   禁止在任何地方 `new PrismaClient()` —— 那样会绕过租户隔离。
 */
function createPrismaClient() {
  return new PrismaClient({
    log: [
      { level: 'warn', emit: 'stdout' },
      { level: 'error', emit: 'stdout' },
    ],
  }).$extends(tenantExtension());
}

export type PrismaWithTenant = ReturnType<typeof createPrismaClient>;

export const PRISMA = Symbol('PRISMA');

export const prismaProvider = {
  provide: PRISMA,
  useFactory: (): PrismaWithTenant => createPrismaClient(),
};

@Global()
@Module({
  providers: [prismaProvider],
  exports: [PRISMA],
})
export class PrismaModule {}
