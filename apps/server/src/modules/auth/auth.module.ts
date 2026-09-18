import { Module } from '@nestjs/common';
import { JwtModule } from '@nestjs/jwt';
import { ConfigModule, ConfigService } from '@nestjs/config';
import { AuthController } from './auth.controller';
import { AuthService } from './auth.service';

@Module({
  imports: [
    JwtModule.registerAsync({
      imports: [ConfigModule],
      inject: [ConfigService],
      useFactory: (cfg: ConfigService) => ({
        secret: cfg.get<string>('JWT_SECRET', 'pinpin-dev-secret-change-me'),
        // ★ 不限制设备 => token 按"常用设备"设计，默认 30 天
        // JWT_EXPIRES 支持秒数(如 2592000)或时间跨度字符串(如 "30d"，见 .env.example)，
        // jsonwebtoken 原生支持这两种格式，切勿用 Number() 包裹（会把 "30d" 转成 NaN）。
        signOptions: {
          expiresIn: (cfg.get<string>('JWT_EXPIRES') ?? '30d') as any,
        },
      }),
    }),
  ],
  controllers: [AuthController],
  providers: [AuthService],
  exports: [AuthService],
})
export class AuthModule {}
