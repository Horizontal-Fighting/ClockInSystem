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
        // JWT_EXPIRES 用**秒数**配置（字符串类型不满足 jsonwebtoken 的 StringValue 类型）
        signOptions: {
          expiresIn: Number(cfg.get<string>('JWT_EXPIRES') ?? 30 * 24 * 3600),
        },
      }),
    }),
  ],
  controllers: [AuthController],
  providers: [AuthService],
  exports: [AuthService],
})
export class AuthModule {}
