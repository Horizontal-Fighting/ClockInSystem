import { Injectable, NestMiddleware } from '@nestjs/common';
import { Request, Response, NextFunction } from 'express';
import { JwtService } from '@nestjs/jwt';
import { TenantContext } from './tenant-context';

export interface AuthUser {
  userId: bigint;
  tenantId: bigint;
  role: number;
}

declare global {
  // eslint-disable-next-line @typescript-eslint/no-namespace
  namespace Express {
    interface Request {
      user?: AuthUser;
    }
  }
}

/**
 * 建立租户上下文的中间件。
 *
 * ★ 为什么用 middleware 而不是 interceptor / guard
 * AsyncLocalStorage 的上下文必须包住**后续整条调用链**。
 * middleware 用 next() 回调能可靠做到；interceptor 走 RxJS 流，
 * 遇到异步操作符时上下文有丢失风险（这类 bug 极难排查）。
 *
 * tenantId 只从**服务端签发的 JWT** 里取，绝不接受请求头/参数传入 —— 见 02 文档 1.4.2 第 2 条。
 */
@Injectable()
export class TenantMiddleware implements NestMiddleware {
  constructor(private readonly jwt: JwtService) {}

  use(req: Request, _res: Response, next: NextFunction) {
    const user = this.parseUser(req);

    if (user) {
      req.user = user;
      TenantContext.run(
        { tenantId: user.tenantId, userId: user.userId, role: user.role },
        () => next(),
      );
    } else {
      // 未登录：不建立上下文。访问任何租户数据时会因拿不到 tenantId 而失败（安全默认）。
      next();
    }
  }

  private parseUser(req: Request): AuthUser | null {
    const raw = req.headers.authorization;
    if (!raw || !raw.startsWith('Bearer ')) {
      return null;
    }
    try {
      const payload = this.jwt.verify<{ sub: string; tid: string; role: number }>(
        raw.slice(7),
      );
      return {
        userId: BigInt(payload.sub),
        tenantId: BigInt(payload.tid),
        role: payload.role ?? 1,
      };
    } catch {
      // token 无效/过期：不抛错，交给 AuthGuard 处理 401，这里只是没上下文
      return null;
    }
  }
}
