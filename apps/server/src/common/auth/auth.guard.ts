import { CanActivate, ExecutionContext, Injectable, ForbiddenException, UnauthorizedException } from '@nestjs/common';
import { Reflector } from '@nestjs/core';
import { Request } from 'express';
import { ROLES_KEY } from './roles.decorator';
import { AuthUser } from '../tenant/tenant.middleware';

/**
 * 登录守卫。依赖 TenantMiddleware 已把 user 挂到 req 上。
 *
 * 角色取值：1家长 2教师 3机构管理员 4平台管理员
 */
@Injectable()
export class AuthGuard implements CanActivate {
  constructor(private readonly reflector: Reflector) {}

  canActivate(context: ExecutionContext): boolean {
    const req = context.switchToHttp().getRequest<Request & { user?: AuthUser }>();

    if (!req.user) {
      throw new UnauthorizedException('未登录或登录已过期');
    }

    const required = this.reflector.getAllAndOverride<number[] | undefined>(ROLES_KEY, [
      context.getHandler(),
      context.getClass(),
    ]);

    if (required?.length && !required.includes(req.user.role)) {
      throw new ForbiddenException('当前角色无权访问该接口');
    }

    return true;
  }
}
