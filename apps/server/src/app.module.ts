import { MiddlewareConsumer, Module, NestModule } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { JwtModule } from '@nestjs/jwt';
import { PrismaModule } from './common/prisma/prisma.module';
import { TenantMiddleware } from './common/tenant/tenant.middleware';
import { AuthModule } from './modules/auth/auth.module';
import { StudentModule } from './modules/student/student.module';
import { HealthController } from './modules/health/health.controller';

@Module({
  imports: [
    ConfigModule.forRoot({ isGlobal: true, envFilePath: ['.env', '../../.env'] }),
    // TenantMiddleware 需要 JwtService 来解析 token，这里全局注册一份
    JwtModule.register({
      secret: process.env.JWT_SECRET ?? 'pinpin-dev-secret-change-me',
    }),
    PrismaModule,
    AuthModule,
    StudentModule,
  ],
  controllers: [HealthController],
})
export class AppModule implements NestModule {
  /**
   * TenantMiddleware 全局生效 —— 所有请求都会建立（或不建立）租户上下文。
   * 这是多租户底座唯一的挂载点，不要在其他地方重复挂载。
   */
  configure(consumer: MiddlewareConsumer) {
    consumer.apply(TenantMiddleware).forRoutes('*');
  }
}
