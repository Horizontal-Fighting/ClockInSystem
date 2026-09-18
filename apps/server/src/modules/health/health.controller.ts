import { Controller, Get, VERSION_NEUTRAL } from '@nestjs/common';
import { Inject } from '@nestjs/common';
import { PRISMA, PrismaWithTenant } from '../../common/prisma/prisma.module';

/**
 * 健康检查。
 * 服务器就绪后第一个要验证的接口：GET /health
 * 用 VERSION_NEUTRAL 让健康检查不受 URI 版本化影响（探针路径保持稳定，不随版本变 /v1/health）。
 */
@Controller({ path: 'health', version: VERSION_NEUTRAL })
export class HealthController {
  constructor(@Inject(PRISMA) private readonly prisma: PrismaWithTenant) {}

  @Get()
  async check() {
    let db: 'up' | 'down' = 'up';
    try {
      await this.prisma.$queryRaw`SELECT 1`;
    } catch {
      db = 'down';
    }
    return {
      status: db === 'up' ? 'ok' : 'degraded',
      db,
      time: new Date().toISOString(),
    };
  }
}
