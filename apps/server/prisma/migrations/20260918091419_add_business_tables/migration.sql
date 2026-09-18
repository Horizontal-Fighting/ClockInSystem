-- CreateTable
CREATE TABLE `material_pack` (
    `id` BIGINT NOT NULL AUTO_INCREMENT,
    `tenantId` BIGINT NOT NULL,
    `name` VARCHAR(128) NOT NULL,
    `coverUrl` VARCHAR(255) NULL,
    `levelId` BIGINT NULL,
    `sort` INTEGER NOT NULL DEFAULT 0,
    `status` TINYINT NOT NULL DEFAULT 1,
    `itemCount` INTEGER NOT NULL DEFAULT 0,
    `createdAt` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    `updatedAt` DATETIME(3) NOT NULL,

    INDEX `material_pack_tenantId_status_idx`(`tenantId`, `status`),
    PRIMARY KEY (`id`)
) DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- CreateTable
CREATE TABLE `pack_item` (
    `id` BIGINT NOT NULL AUTO_INCREMENT,
    `tenantId` BIGINT NOT NULL,
    `packId` BIGINT NOT NULL,
    `materialId` BIGINT NOT NULL,
    `sort` INTEGER NOT NULL DEFAULT 0,
    `required` TINYINT NOT NULL DEFAULT 1,
    `createdAt` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),

    INDEX `pack_item_tenantId_packId_idx`(`tenantId`, `packId`),
    UNIQUE INDEX `pack_item_packId_materialId_key`(`packId`, `materialId`),
    PRIMARY KEY (`id`)
) DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- CreateTable
CREATE TABLE `task` (
    `id` BIGINT NOT NULL AUTO_INCREMENT,
    `tenantId` BIGINT NOT NULL,
    `title` VARCHAR(128) NOT NULL,
    `packId` BIGINT NULL,
    `teacherId` BIGINT NULL,
    `evalMode` TINYINT NOT NULL DEFAULT 0,
    `publishAt` DATETIME(3) NULL,
    `dueAt` DATETIME(3) NULL,
    `requireAll` TINYINT NOT NULL DEFAULT 0,
    `allowMakeup` TINYINT NOT NULL DEFAULT 0,
    `status` TINYINT NOT NULL DEFAULT 1,
    `targetType` TINYINT NULL,
    `coursewareId` BIGINT NULL,
    `requireCourseware` TINYINT NOT NULL DEFAULT 0,
    `createdAt` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    `updatedAt` DATETIME(3) NOT NULL,

    INDEX `task_tenantId_status_idx`(`tenantId`, `status`),
    PRIMARY KEY (`id`)
) DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- CreateTable
CREATE TABLE `task_target` (
    `id` BIGINT NOT NULL AUTO_INCREMENT,
    `tenantId` BIGINT NOT NULL,
    `taskId` BIGINT NOT NULL,
    `targetType` TINYINT NOT NULL,
    `targetId` BIGINT NOT NULL,

    INDEX `task_target_tenantId_targetType_targetId_idx`(`tenantId`, `targetType`, `targetId`),
    UNIQUE INDEX `task_target_taskId_targetType_targetId_key`(`taskId`, `targetType`, `targetId`),
    PRIMARY KEY (`id`)
) DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- CreateTable
CREATE TABLE `courseware` (
    `id` BIGINT NOT NULL AUTO_INCREMENT,
    `tenantId` BIGINT NOT NULL,
    `title` VARCHAR(128) NOT NULL,
    `coverUrl` VARCHAR(255) NULL,
    `intro` VARCHAR(512) NULL,
    `levelId` BIGINT NULL,
    `blockCount` INTEGER NOT NULL DEFAULT 0,
    `audioDurationTotal` INTEGER NOT NULL DEFAULT 0,
    `status` TINYINT NOT NULL DEFAULT 1,
    `createdBy` BIGINT NULL,
    `createdAt` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    `updatedAt` DATETIME(3) NOT NULL,

    INDEX `courseware_tenantId_status_idx`(`tenantId`, `status`),
    PRIMARY KEY (`id`)
) DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- CreateTable
CREATE TABLE `courseware_block` (
    `id` BIGINT NOT NULL AUTO_INCREMENT,
    `tenantId` BIGINT NOT NULL,
    `coursewareId` BIGINT NOT NULL,
    `blockType` TINYINT NOT NULL,
    `sort` INTEGER NOT NULL DEFAULT 0,
    `textContent` TEXT NULL,
    `assetUrl` VARCHAR(255) NULL,
    `durationMs` INTEGER NULL,
    `refMaterialId` BIGINT NULL,
    `showTitle` VARCHAR(128) NULL,
    `createdAt` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    `updatedAt` DATETIME(3) NOT NULL,

    INDEX `courseware_block_coursewareId_sort_idx`(`coursewareId`, `sort`),
    PRIMARY KEY (`id`)
) DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- CreateTable
CREATE TABLE `courseware_progress` (
    `id` BIGINT NOT NULL AUTO_INCREMENT,
    `tenantId` BIGINT NOT NULL,
    `studentId` BIGINT NOT NULL,
    `coursewareId` BIGINT NOT NULL,
    `lastBlockSort` INTEGER NOT NULL DEFAULT 0,
    `finished` TINYINT NOT NULL DEFAULT 0,
    `finishedAt` DATETIME(3) NULL,
    `createdAt` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    `updatedAt` DATETIME(3) NOT NULL,

    INDEX `courseware_progress_tenantId_coursewareId_idx`(`tenantId`, `coursewareId`),
    UNIQUE INDEX `courseware_progress_studentId_coursewareId_key`(`studentId`, `coursewareId`),
    PRIMARY KEY (`id`)
) DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- CreateTable
CREATE TABLE `media_file` (
    `id` BIGINT NOT NULL AUTO_INCREMENT,
    `tenantId` BIGINT NOT NULL,
    `bucket` VARCHAR(64) NULL,
    `objectKey` VARCHAR(255) NOT NULL,
    `mime` VARCHAR(64) NULL,
    `sizeBytes` INTEGER NULL,
    `durationMs` INTEGER NULL,
    `createdAt` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),

    INDEX `media_file_tenantId_id_idx`(`tenantId`, `id`),
    PRIMARY KEY (`id`)
) DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- CreateTable
CREATE TABLE `checkin_record` (
    `id` BIGINT NOT NULL AUTO_INCREMENT,
    `tenantId` BIGINT NOT NULL,
    `taskId` BIGINT NULL,
    `studentId` BIGINT NOT NULL,
    `dueDate` DATE NOT NULL,
    `status` TINYINT NOT NULL DEFAULT 1,
    `itemTotal` INTEGER NOT NULL DEFAULT 0,
    `itemDone` INTEGER NOT NULL DEFAULT 0,
    `avgScore` DECIMAL(5, 2) NULL,
    `bestScore` DECIMAL(5, 2) NULL,
    `submittedAt` DATETIME(3) NULL,
    `reviewedAt` DATETIME(3) NULL,
    `createdAt` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    `updatedAt` DATETIME(3) NOT NULL,

    INDEX `checkin_record_tenantId_studentId_dueDate_idx`(`tenantId`, `studentId`, `dueDate`),
    PRIMARY KEY (`id`)
) DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- CreateTable
CREATE TABLE `checkin_item` (
    `id` BIGINT NOT NULL AUTO_INCREMENT,
    `tenantId` BIGINT NOT NULL,
    `recordId` BIGINT NOT NULL,
    `materialId` BIGINT NOT NULL,
    `studentId` BIGINT NOT NULL,
    `dueDate` DATE NOT NULL,
    `audioFileId` BIGINT NULL,
    `durationMs` INTEGER NULL,
    `volumeAvg` INTEGER NULL,
    `attemptCount` INTEGER NOT NULL DEFAULT 1,
    `score` DECIMAL(5, 2) NULL,
    `accuracy` DECIMAL(5, 2) NULL,
    `fluency` DECIMAL(5, 2) NULL,
    `completion` DECIMAL(5, 2) NULL,
    `star` TINYINT NULL,
    `weakPhonemes` JSON NULL,
    `evalStatus` TINYINT NOT NULL DEFAULT 1,
    `evalProvider` VARCHAR(32) NULL,
    `evalCostMs` INTEGER NULL,
    `isSelected` TINYINT NOT NULL DEFAULT 0,
    `createdAt` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    `updatedAt` DATETIME(3) NOT NULL,

    INDEX `checkin_item_tenantId_recordId_idx`(`tenantId`, `recordId`),
    INDEX `checkin_item_tenantId_studentId_dueDate_idx`(`tenantId`, `studentId`, `dueDate`),
    PRIMARY KEY (`id`)
) DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- CreateTable
CREATE TABLE `score_detail` (
    `id` BIGINT NOT NULL AUTO_INCREMENT,
    `tenantId` BIGINT NOT NULL,
    `itemId` BIGINT NOT NULL,
    `provider` VARCHAR(32) NOT NULL,
    `rawJson` JSON NOT NULL,
    `suggestedScore` DECIMAL(5, 2) NULL,
    `createdAt` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),

    UNIQUE INDEX `score_detail_itemId_key`(`itemId`),
    INDEX `score_detail_tenantId_itemId_idx`(`tenantId`, `itemId`),
    PRIMARY KEY (`id`)
) DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- CreateTable
CREATE TABLE `review` (
    `id` BIGINT NOT NULL AUTO_INCREMENT,
    `tenantId` BIGINT NOT NULL,
    `recordId` BIGINT NOT NULL,
    `itemId` BIGINT NULL,
    `teacherId` BIGINT NULL,
    `studentId` BIGINT NOT NULL,
    `tagIds` JSON NULL,
    `text` VARCHAR(500) NULL,
    `audioFileId` BIGINT NULL,
    `needRedo` TINYINT NOT NULL DEFAULT 0,
    `isRead` TINYINT NOT NULL DEFAULT 0,
    `createdAt` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),

    INDEX `review_tenantId_recordId_idx`(`tenantId`, `recordId`),
    INDEX `review_tenantId_studentId_idx`(`tenantId`, `studentId`),
    PRIMARY KEY (`id`)
) DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- CreateTable
CREATE TABLE `student_stat` (
    `id` BIGINT NOT NULL AUTO_INCREMENT,
    `tenantId` BIGINT NOT NULL,
    `studentId` BIGINT NOT NULL,
    `continuousDays` INTEGER NOT NULL DEFAULT 0,
    `maxContinuousDays` INTEGER NOT NULL DEFAULT 0,
    `totalDays` INTEGER NOT NULL DEFAULT 0,
    `totalDurationMs` INTEGER NOT NULL DEFAULT 0,
    `totalStars` INTEGER NOT NULL DEFAULT 0,
    `avgScore30d` DECIMAL(5, 2) NULL,
    `lastCheckinDate` DATE NULL,
    `trend` TINYINT NOT NULL DEFAULT 2,
    `updatedAt` DATETIME(3) NOT NULL,

    UNIQUE INDEX `student_stat_studentId_key`(`studentId`),
    INDEX `student_stat_tenantId_studentId_idx`(`tenantId`, `studentId`),
    PRIMARY KEY (`id`)
) DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- CreateTable
CREATE TABLE `daily_class_stat` (
    `id` BIGINT NOT NULL AUTO_INCREMENT,
    `tenantId` BIGINT NOT NULL,
    `groupId` BIGINT NOT NULL,
    `date` DATE NOT NULL,
    `submittedCount` INTEGER NOT NULL DEFAULT 0,
    `reviewedCount` INTEGER NOT NULL DEFAULT 0,
    `avgScore` DECIMAL(5, 2) NULL,
    `createdAt` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    `updatedAt` DATETIME(3) NOT NULL,

    UNIQUE INDEX `daily_class_stat_tenantId_groupId_date_key`(`tenantId`, `groupId`, `date`),
    PRIMARY KEY (`id`)
) DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- CreateTable
CREATE TABLE `sys_config` (
    `id` BIGINT NOT NULL AUTO_INCREMENT,
    `tenantId` BIGINT NOT NULL,
    `configKey` VARCHAR(64) NOT NULL,
    `configValue` JSON NOT NULL,
    `remark` VARCHAR(255) NULL,
    `updatedBy` BIGINT NULL,
    `updatedAt` DATETIME(3) NOT NULL,

    UNIQUE INDEX `sys_config_tenantId_configKey_key`(`tenantId`, `configKey`),
    PRIMARY KEY (`id`)
) DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- CreateTable
CREATE TABLE `material_phoneme` (
    `id` BIGINT NOT NULL AUTO_INCREMENT,
    `tenantId` BIGINT NOT NULL,
    `symbol` VARCHAR(32) NOT NULL,
    `standardAudioUrl` VARCHAR(255) NULL,
    `createdAt` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),

    UNIQUE INDEX `material_phoneme_tenantId_symbol_key`(`tenantId`, `symbol`),
    PRIMARY KEY (`id`)
) DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- CreateTable
CREATE TABLE `tenant_usage` (
    `id` BIGINT NOT NULL AUTO_INCREMENT,
    `tenantId` BIGINT NOT NULL,
    `date` DATE NOT NULL,
    `evalCount` INTEGER NOT NULL DEFAULT 0,
    `storageBytes` BIGINT NOT NULL DEFAULT 0,
    `activeStudents` INTEGER NOT NULL DEFAULT 0,
    `activeTeachers` INTEGER NOT NULL DEFAULT 0,
    `createdAt` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    `updatedAt` DATETIME(3) NOT NULL,

    UNIQUE INDEX `tenant_usage_tenantId_date_key`(`tenantId`, `date`),
    PRIMARY KEY (`id`)
) DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- CreateTable
CREATE TABLE `notification` (
    `id` BIGINT NOT NULL AUTO_INCREMENT,
    `tenantId` BIGINT NOT NULL,
    `userId` BIGINT NULL,
    `templateId` VARCHAR(64) NULL,
    `status` TINYINT NOT NULL DEFAULT 0,
    `wxCode` VARCHAR(64) NULL,
    `content` VARCHAR(512) NULL,
    `createdAt` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),

    INDEX `notification_tenantId_userId_idx`(`tenantId`, `userId`),
    PRIMARY KEY (`id`)
) DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- CreateTable
CREATE TABLE `operation_log` (
    `id` BIGINT NOT NULL AUTO_INCREMENT,
    `tenantId` BIGINT NOT NULL,
    `actorUserId` BIGINT NULL,
    `action` VARCHAR(64) NOT NULL,
    `targetType` VARCHAR(32) NULL,
    `targetId` BIGINT NULL,
    `detail` JSON NULL,
    `createdAt` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),

    INDEX `operation_log_tenantId_action_idx`(`tenantId`, `action`),
    PRIMARY KEY (`id`)
) DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- AddForeignKey
ALTER TABLE `pack_item` ADD CONSTRAINT `pack_item_packId_fkey` FOREIGN KEY (`packId`) REFERENCES `material_pack`(`id`) ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE `task_target` ADD CONSTRAINT `task_target_taskId_fkey` FOREIGN KEY (`taskId`) REFERENCES `task`(`id`) ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE `courseware_block` ADD CONSTRAINT `courseware_block_coursewareId_fkey` FOREIGN KEY (`coursewareId`) REFERENCES `courseware`(`id`) ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE `checkin_item` ADD CONSTRAINT `checkin_item_recordId_fkey` FOREIGN KEY (`recordId`) REFERENCES `checkin_record`(`id`) ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE `checkin_item` ADD CONSTRAINT `checkin_item_audioFileId_fkey` FOREIGN KEY (`audioFileId`) REFERENCES `media_file`(`id`) ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE `score_detail` ADD CONSTRAINT `score_detail_itemId_fkey` FOREIGN KEY (`itemId`) REFERENCES `checkin_item`(`id`) ON DELETE RESTRICT ON UPDATE CASCADE;
