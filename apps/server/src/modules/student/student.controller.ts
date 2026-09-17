import { Body, Controller, Get, Param, ParseIntPipe, Post, UseGuards } from '@nestjs/common';
import { AuthGuard } from '../../common/auth/auth.guard';
import { StudentService } from './student.service';

class CreateStudentDto {
  nickname!: string;
  avatarPreset?: string;
  levelId?: number;
}

@Controller('students')
@UseGuards(AuthGuard)
export class StudentController {
  constructor(private readonly students: StudentService) {}

  @Get()
  list() {
    return this.students.list();
  }

  @Get(':id')
  detail(@Param('id', ParseIntPipe) id: number) {
    return this.students.detail(BigInt(id));
  }

  @Post()
  create(@Body() dto: CreateStudentDto) {
    return this.students.create({
      nickname: dto.nickname,
      avatarPreset: dto.avatarPreset,
      levelId: dto.levelId ? BigInt(dto.levelId) : undefined,
    });
  }
}
