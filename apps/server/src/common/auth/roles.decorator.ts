import { SetMetadata } from '@nestjs/common';

/** 角色：1家长 2教师 3机构管理员 4平台管理员 */
export const ROLE = {
  PARENT: 1,
  TEACHER: 2,
  ORG_ADMIN: 3,
  PLATFORM_ADMIN: 4,
} as const;

/** 用法：@Roles(ROLE.TEACHER, ROLE.ORG_ADMIN) */
export const ROLES_KEY = 'roles';
export const Roles = (...roles: number[]) => SetMetadata(ROLES_KEY, roles);
