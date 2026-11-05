# CampusTrain 报名规则

> 仅记录 enrollment-service 和其调用的培训校验代码明确执行的条件。

## 报名入口和身份

### 入口

报名使用 `POST /enrollment/create`，请求体只需要 `trainingId`。服务从 Gateway 用户上下文取得当前用户 ID；缺少身份时返回 401。Gateway 角色存在且不是 `STUDENT` 时拒绝，远程用户还必须是启用状态且角色为 `STUDENT`。

Source: `CampusTrain/enrollment-service/src/main/java/com/campustrain/enrollmentservice/service/impl/EnrollmentServiceImpl.java#EnrollmentServiceImpl.createEnrollment`
Source: `CampusTrain/enrollment-service/src/main/java/com/campustrain/enrollmentservice/service/impl/EnrollmentServiceImpl.java#EnrollmentServiceImpl.getCurrentUserId`
Source: `CampusTrain/enrollment-service/src/main/java/com/campustrain/enrollmentservice/service/impl/EnrollmentServiceImpl.java#EnrollmentServiceImpl.validateUser`

## 时间和状态条件

培训必须存在，状态必须是 `1`（报名中）。当前时间不能早于 `enrollStartTime`，也不能晚于 `enrollEndTime`；空的开始或结束时间不会触发对应比较。培训不在报名状态或时间窗口外时，报名被拒绝。

Source: `CampusTrain/enrollment-service/src/main/java/com/campustrain/enrollmentservice/service/impl/EnrollmentServiceImpl.java#EnrollmentServiceImpl.validateTraining`

## 容量和重复报名

当容量为空，或 `enrolledCount >= capacity` 时，报名被拒绝。服务同时使用 Redis 预约和培训服务计数调用防止超卖；预约返回重复或已满也会拒绝。数据库中存在同一用户同一培训的已报名记录时，返回“请勿重复报名”。

Source: `CampusTrain/enrollment-service/src/main/java/com/campustrain/enrollmentservice/service/impl/EnrollmentServiceImpl.java#EnrollmentServiceImpl.validateTraining`
Source: `CampusTrain/enrollment-service/src/main/java/com/campustrain/enrollmentservice/service/impl/EnrollmentServiceImpl.java#EnrollmentServiceImpl.hasActiveEnrollment`
Source: `CampusTrain/enrollment-service/src/main/java/com/campustrain/enrollmentservice/service/impl/EnrollmentServiceImpl.java#EnrollmentServiceImpl.createEnrollment`

## 成功结果

成功报名的记录状态为 `1`（`ENROLLED`），写入报名时间；同时创建报名成功 Outbox 事件。若历史记录状态为 `0`（`CANCELLED`），通过所有当前校验后会将原记录重新激活，而不是新建另一条记录。

Source: `CampusTrain/enrollment-service/src/main/java/com/campustrain/enrollmentservice/service/impl/EnrollmentServiceImpl.java#EnrollmentServiceImpl.createEnrollment`
Source: `CampusTrain/enrollment-service/src/main/java/com/campustrain/enrollmentservice/entity/EnrollmentStatus.java#EnrollmentStatus`

## 未规定的事项

源码没有规定候补名单、人工加名、跨培训名额转移、报名费用、通知时限或报名成功后的外部承诺。不能从容量字段推断这些政策。

