# CampusTrain 学习与进度规则

> 规则来源为 learning-service 的实际服务、进度存储和配置；没有源码依据的学习政策不在本文推断。

## 身份和有效报名

学习接口要求存在登录身份且角色为 `STUDENT`。查询培训进度、章节进度或课时进度前，服务会校验用户对相关培训存在有效报名；否则返回 403“没有有效报名”。

Source: `CampusTrain/learning-service/src/main/java/com/campustrain/learningservice/service/impl/LearningServiceImpl.java#LearningServiceImpl.userId`
Source: `CampusTrain/learning-service/src/main/java/com/campustrain/learningservice/service/impl/LearningServiceImpl.java#LearningServiceImpl.requireEnrollment`

## 培训和章节完成度

培训进度由培训目录中的课时总数和已完成课时数计算，返回 `totalLessons`、`completedLessons` 和 `progressRatio`。章节进度只统计指定章节中的课时。目录为空时，完成比例为 `0`。

Source: `CampusTrain/learning-service/src/main/java/com/campustrain/learningservice/service/impl/LearningServiceImpl.java#LearningServiceImpl.summary`
Source: `CampusTrain/learning-service/src/main/java/com/campustrain/learningservice/vo/LearningSummaryVO.java#LearningSummaryVO`

## 视频进度

上报视频进度前，课时必须存在、用户必须有效报名、课时类型必须是视频、视频必须绑定对象且视频时长为正数。`progressSeconds` 不能为负数，且不能超过视频时长；进度更新不会倒退。完成阈值为 `ceil(videoDuration * completeRatio)`，当前 Nacos 配置 `complete-ratio` 为 `0.90`。

Source: `CampusTrain/learning-service/src/main/java/com/campustrain/learningservice/service/impl/LearningServiceImpl.java#LearningServiceImpl.updateLearningProgress`
Source: `CampusTrain/learning-service/src/main/java/com/campustrain/learningservice/service/impl/LearningServiceImpl.java#LearningServiceImpl.requireVideo`
Source: `CampusTrain/learning-service/src/main/java/com/campustrain/learningservice/service/LearningProgressStore.java#LearningProgressStore.updateProgress`
Source: `CampusTrain/config/nacos/learning-service-dev.yaml#campustrain.learning.complete-ratio`

## 图文课时

图文课时不能走视频播放或视频进度上报。只有 `lessonType=1` 的图文课时允许调用显式完成操作 `POST /learning/complete/{lessonId}`；视频课时不能使用该显式完成入口。

Source: `CampusTrain/learning-service/src/main/java/com/campustrain/learningservice/service/impl/LearningServiceImpl.java#LearningServiceImpl.completeTextLesson`
Source: `CampusTrain/learning-service/src/main/java/com/campustrain/learningservice/service/impl/LearningServiceImpl.java#LearningServiceImpl.requireVideo`

## 未规定的事项

### 客服回答边界

源码没有定义学习时长奖励、证书、考试通过线、暂停规则、跨设备同步承诺或人工修正流程。当前知识库不支持回答这些问题。

