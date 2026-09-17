import { Body, Controller, Post } from '@nestjs/common';
import { AuthService } from './auth.service';

class LoginDto {
  username!: string;
  password!: string;
  /** 可选。一个账号属于多个机构时传，用来指定进入哪个机构 */
  tenantId?: string;
}

@Controller('auth')
export class AuthController {
  constructor(private readonly auth: AuthService) {}

  /**
   * 账号密码登录。
   * 返回 token；若该账号属于多个机构且未指定 tenantId，返回 needChooseTenant + 机构列表。
   */
  @Post('login')
  async login(@Body() dto: LoginDto) {
    return this.auth.login(
      dto.username,
      dto.password,
      dto.tenantId ? BigInt(dto.tenantId) : undefined,
    );
  }
}
