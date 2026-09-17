import { NestFactory } from '@nestjs/core';
import { ValidationPipe, VersioningType } from '@nestjs/common';
import { AppModule } from './app.module';

/**
 * ★ BigInt 序列化兜底
 * Prisma 把 MySQL BIGINT 映射为 JS BigInt，而 JSON.stringify 不认识 BigInt，
 * 默认会抛 "Do not know how to serialize a BigInt"。
 * 这里统一转成 Number —— 安全前提：ID 远小于 Number.MAX_SAFE_INTEGER(2^53)。
 */
(BigInt.prototype as unknown as { toJSON: () => number }).toJSON = function () {
  return Number(this);
};

async function bootstrap() {
  const app = await NestFactory.create(AppModule);

  app.enableVersioning({ type: VersioningType.URI, defaultVersion: '1' });
  app.setGlobalPrefix('api', { exclude: ['health'] });

  app.useGlobalPipes(
    new ValidationPipe({
      whitelist: true,           // 剥掉 DTO 未声明的字段（防前端伪造 tenantId 等）
      forbidNonWhitelisted: true,
      transform: true,
    }),
  );

  app.enableCors();

  const port = process.env.PORT ?? 3000;
  await app.listen(port);
  // eslint-disable-next-line no-console
  console.log(`API ready: http://localhost:${port}/health`);
}

void bootstrap();
