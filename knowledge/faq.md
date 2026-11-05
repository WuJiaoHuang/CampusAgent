# CampusTrain 课程与学习 FAQ

> 文档用途：为后续 RAG 分块提供可核验的问答材料。
> 规则来源只覆盖当前源码明确实现的行为；没有源码依据的政策不在本文件中回答。

## 课程详情和目录

### 如何查询培训详情？

调用 Gateway 的 `GET /training/get/{trainingId}`。返回培训 ID、标题、描述、容量、已报名人数、状态和时间字段。
培训不存在时，training-service 抛出“培训不存在”的业务错误。

Source: `CampusTrain/training-service/src/main/java/com/campustrain/trainingservice/service/impl/TrainingServiceImpl.java#TrainingServiceImpl.getTrainingDetail`

### 如何查看培训的课程、章节和课时？

调用 `GET /training/get/catalog/{trainingId}`。目录按课程、章节、课时树形返回，并按各自的 `sort` 升序、再按 ID 升序排列；没有课程时返回空课程列表。培训不存在时返回业务错误。

Source: `CampusTrain/training-service/src/main/java/com/campustrain/trainingservice/service/impl/TrainingServiceImpl.java#TrainingServiceImpl.getTrainingCatalog`

### 课时类型如何区分？

目录 VO 明确规定 `lessonType=0` 为视频课时，`lessonType=1` 为图文课时。该字段只描述类型，不能据此推断完成所需时间或是否允许报名。

Source: `CampusTrain/training-service/src/main/java/com/campustrain/trainingservice/vo/LessonCatalogVO.java#LessonCatalogVO.lessonType`

## 报名和学习

### 如何查看我的报名？

调用 `GET /enrollment/list/mine?page={page}&size={size}`，可选 `status` 过滤。返回分页记录；状态 `1` 是已报名，状态 `0` 是已取消。必须先登录。

Source: `CampusTrain/enrollment-service/src/main/java/com/campustrain/enrollmentservice/service/impl/EnrollmentServiceImpl.java#EnrollmentServiceImpl.getMyEnrollments`
Source: `CampusTrain/enrollment-service/src/main/java/com/campustrain/enrollmentservice/entity/EnrollmentStatus.java#EnrollmentStatus`

### 如何查看学习进度？

已报名学生可查询培训完成度 `GET /learning/get/training-progress/{trainingId}`，或查询课时进度 `GET /learning/get-progress/{lessonId}`。学习服务会校验学生身份和有效报名；没有有效报名时返回 403 业务错误。

Source: `CampusTrain/learning-service/src/main/java/com/campustrain/learningservice/service/impl/LearningServiceImpl.java#LearningServiceImpl.getTrainingProgress`
Source: `CampusTrain/learning-service/src/main/java/com/campustrain/learningservice/service/impl/LearningServiceImpl.java#LearningServiceImpl.getLearningProgress`

## 明确不支持的回答

当前源码没有规定证书发放、补课政策、逾期处理、客服承诺、评分规则或自然语言课程推荐。Agent 不应根据本知识库编造这些政策。

