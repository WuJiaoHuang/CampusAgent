# CampusTrain 取消报名规则

> 本文只描述当前 `cancelEnrollment` 的实际行为；本阶段只做知识整理，不调用取消接口。

## 取消条件

调用 `POST /enrollment/cancel/{enrollmentId}`。用户必须已登录，且报名记录必须存在并属于当前用户。记录状态必须为 `1`（`ENROLLED`）；否则返回“报名已取消”。源码没有按培训开始时间、学习进度或其他业务日期额外限制取消。

Source: `CampusTrain/enrollment-service/src/main/java/com/campustrain/enrollmentservice/service/impl/EnrollmentServiceImpl.java#EnrollmentServiceImpl.cancelEnrollment`
Source: `CampusTrain/enrollment-service/src/main/java/com/campustrain/enrollmentservice/entity/EnrollmentStatus.java#EnrollmentStatus`

## 状态和名额变化

成功取消时，记录状态更新为 `0`（`CANCELLED`），更新修改时间；培训服务报名人数递减，Redis 报名预约释放。任一依赖操作失败时，服务尝试补偿恢复计数或预约，并向调用方返回错误，不能把失败当成成功。

Source: `CampusTrain/enrollment-service/src/main/java/com/campustrain/enrollmentservice/service/impl/EnrollmentServiceImpl.java#EnrollmentServiceImpl.cancelEnrollment`
Source: `CampusTrain/enrollment-service/src/main/java/com/campustrain/enrollmentservice/service/impl/EnrollmentServiceImpl.java#EnrollmentServiceImpl.restoreReservation`

## 取消后的重新报名

取消后的历史记录仍存在，状态为 `0`。只要重新报名时满足学生身份、培训状态、报名时间窗口和容量等当前校验，`createEnrollment` 会把该记录改回 `1` 并更新报名时间；这不是无条件保证，任何校验失败都会拒绝。

Source: `CampusTrain/enrollment-service/src/main/java/com/campustrain/enrollmentservice/service/impl/EnrollmentServiceImpl.java#EnrollmentServiceImpl.createEnrollment`

## 未规定的事项

### 客服回答边界

源码没有规定退款、取消截止日期、学习记录是否删除、取消通知内容或重新报名次数限制。Agent 必须明确告知这些事项未由当前代码定义。

