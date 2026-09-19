# api/models.py
"""
API请求和响应数据模型

使用Pydantic进行数据验证和序列化。
"""

from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field, HttpUrl, validator


# ============================================================================
# 选项模型
# ============================================================================

class OptionItem(BaseModel):
    """题目选项"""
    value: Any = Field(..., description="选项值/序号")
    label: Optional[str] = Field(None, description="选项文本标签（如果有的话）")

    class Config:
        # 允许选项值为数字或字符串
        arbitrary_types_allowed = True


# ============================================================================
# 通用响应模型
# ============================================================================

class BaseResponse(BaseModel):
    """基础响应模型"""
    success: bool = Field(..., description="请求是否成功")
    message: str = Field("", description="响应消息")


class DataResponse(BaseResponse):
    """带数据的响应模型"""
    data: Any = Field(None, description="响应数据")


# ============================================================================
# 问卷分析相关模型
# ============================================================================

class AnalyzeRequest(BaseModel):
    """问卷分析请求"""
    url: HttpUrl = Field(..., description="问卷URL", example="https://v.wjx.cn/vm/eLeS3jD.aspx")
    use_ai: bool = Field(False, description="是否使用AI进行反向题识别")
    analysis_mode: Literal["standard", "proportional"] = Field(
        "standard",
        description="解析模式；proportional仅解析页面结构，不执行正反向题识别",
    )


class QuestionResponse(BaseModel):
    """题目信息"""
    id: str = Field(..., description="题目ID", example="q1")
    type: str = Field(..., description="题型", example="radio")
    label: str = Field(..., description="题目文本", example="*1.您的性别")
    options: List[Any] = Field(default_factory=list, description="选项列表（值或对象）")
    required: bool = Field(True, description="是否必填")
    is_scale: bool = Field(False, description="是否为量表题（rating/nps/matrix/radio scale）")
    is_reverse: bool = Field(False, description="是否反向题")
    reverse_confidence: Optional[float] = Field(None, description="反向题置信度")
    detection_method: Optional[str] = Field(None, description="检测方法（ai 或 keyword）")
    positive_values: Optional[List[Any]] = Field(None, description="积极态度对应的选项值列表")
    negative_values: Optional[List[Any]] = Field(None, description="消极态度对应的选项值列表")
    ratio_eligible: bool = Field(False, description="是否支持按选项比例配置")
    ratio_kind: Optional[Literal["single", "multiple"]] = Field(None, description="比例规则类型")
    selection_min: Optional[int] = Field(None, description="多选题每份最少选择数量")
    selection_max: Optional[int] = Field(None, description="多选题每份最多选择数量")
    parent_question_id: Optional[str] = Field(None, description="矩阵小题所属父题ID")
    ratio_display_key: Optional[str] = Field(None, description="按问卷实际顺序生成的比例配置显示题号")
    display_order: int = Field(0, description="问卷页面从上到下的实际题序")
    ratio_zero_values: List[Any] = Field(default_factory=list, description="必须固定为0%的填空选项值")


class AnalyzeResponse(BaseModel):
    """问卷分析响应"""
    task_id: str = Field(..., description="任务ID（已落库，submit接口凭此ID提交，无需重新传url分析）")
    activity_id: str = Field(..., description="活动ID")
    url: str = Field(..., description="问卷URL")
    title: str = Field("", description="问卷标题")
    description: str = Field("", description="问卷介绍/说明")
    total_questions: int = Field(..., description="题目总数")
    question_types: Dict[str, int] = Field(default_factory=dict, description="题型统计")
    questions: List[QuestionResponse] = Field(default_factory=list, description="题目列表")
    scale_questions: int = Field(0, description="量表题数量")
    reverse_items: List[str] = Field(default_factory=list, description="反向题ID列表")
    detection_method: str = Field("keyword", description="使用的检测方法（keyword、ai 或 structure）")


# ============================================================================
# 问卷提交相关模型
# ============================================================================

class SubmitConfig(BaseModel):
    """提交配置"""
    attitude: Literal["positive", "negative"] = Field(
        "positive",
        description="回答态度：positive(积极) 或 negative(消极)"
    )
    add_variation: bool = Field(False, description="是否穿插变化")
    variation_ratio: float = Field(
        0.05,
        ge=0.01,
        le=0.30,
        description="变化比例（0.01-0.30）"
    )
    debug: bool = Field(
        False,
        description="是否开启浏览器调试模式（显示浏览器窗口，便于观察填写过程）；关闭则以无头模式后台提交"
    )
    max_submit_attempts: int = Field(
        10, ge=1, le=10, description="每个提交序号的最大尝试次数；失败不会消费下一份"
    )


class ProxyConfig(BaseModel):
    """单个提交任务使用的代理策略（不包含供应商凭据）。"""

    enabled: bool = Field(False, description="是否为该任务启用动态代理")
    provider: Literal["kuaidaili"] = Field("kuaidaili", description="代理供应商")
    area: str = Field("", max_length=64, description="目标地区，如南京、杭州市")
    carrier: Literal[0, 1, 2, 3] = Field(
        0, description="运营商：0不限、1联通、2电信、3移动"
    )
    rotate_per_submission: bool = Field(True, description="是否每份问卷重新提取代理")
    dedup: bool = Field(True, description="是否过滤当天已经提取过的IP")
    verify_exit: bool = Field(True, description="是否通过浏览器验证实际出口IP和地区")
    location_match: Literal["strict", "relaxed"] = Field(
        "relaxed", description="地区匹配策略"
    )
    required: bool = Field(True, description="代理失败时是否禁止回退到直连")
    max_acquire_attempts: int = Field(10, ge=1, le=10, description="单份最大代理获取次数")

    @validator("area")
    def validate_area(cls, value, values):
        normalized = " ".join((value or "").strip().split())
        if values.get("enabled") and not normalized:
            raise ValueError("启用代理时必须指定area")
        return normalized


class AITextAnswerConfig(BaseModel):
    """任务开始前预生成单行和多行文本题答案的配置。"""

    enabled: bool = Field(False, description="是否使用AI批量生成单行和多行文本答案")
    batch_size: int = Field(20, ge=1, le=50, description="单次模型调用生成的提交份数")
    max_generation_attempts: int = Field(
        3, ge=1, le=5, description="每个批次格式错误或调用失败时的最大尝试次数"
    )
    max_submit_attempts: int = Field(
        10, ge=1, le=10, description="每个成功提交序号的最大尝试次数；失败不会消费下一份"
    )


class ProportionOptionConfig(BaseModel):
    value: Any = Field(..., description="分析结果中的真实选项值")
    percentage: float = Field(..., ge=0, le=100, description="该选项目标百分比")


class ProportionQuestionConfig(BaseModel):
    question_id: str
    enabled: bool = True
    options: List[ProportionOptionConfig]


class ProportionConfig(BaseModel):
    questions: List[ProportionQuestionConfig] = Field(..., min_items=1)
    seed: int = Field(0, ge=0, le=2147483647, description="答案计划打乱种子")
    max_submit_attempts: int = Field(10, ge=1, le=10, description="比例计划单份最大提交次数")


class SubmitRequest(BaseModel):
    """问卷提交请求

    task_id 对应 analyze_questionnaire 返回的任务ID。提交时直接读取该任务
    落库的 analyzed_schema 生成答案，不会重新访问问卷页面或重新分析。
    """
    task_id: str = Field(..., description="任务ID（由 /analyze 接口返回）")
    count: int = Field(..., ge=1, le=1000, description="提交份数（1-1000）")
    mode: Literal["random", "high_reliability", "proportional"] = Field(
        ...,
        description="提交模式：random、high_reliability 或 proportional"
    )
    config: Optional[SubmitConfig] = Field(
        None,
        description="模式配置（mode为high_reliability时必填）"
    )
    proxy: Optional[ProxyConfig] = Field(
        None,
        description="任务代理配置；省略时禁用代理，只有enabled=true才使用服务端代理凭据"
    )
    ai_text: Optional[AITextAnswerConfig] = Field(
        None,
        description="文本题AI预生成配置；省略或disabled时继续使用原有回答策略"
    )
    proportion_config: Optional[ProportionConfig] = Field(
        None, description="proportional模式的题目选项比例配置"
    )

    @validator('config')
    def validate_config(cls, v, values):
        """验证config字段"""
        mode = values.get('mode')
        if mode == 'high_reliability' and v is None:
            raise ValueError('high_reliability模式必须提供config配置')
        return v

    @validator('proportion_config', always=True)
    def validate_proportion_config(cls, v, values):
        if values.get('mode') == 'proportional' and v is None:
            raise ValueError('proportional模式必须提供proportion_config')
        return v


class TaskConfigUpdate(BaseModel):
    """Editable execution settings for an existing questionnaire task."""
    mode: Optional[Literal["random", "high_reliability", "proportional"]] = None
    attitude: Optional[Literal["positive", "negative"]] = None
    add_variation: Optional[bool] = None
    variation_ratio: Optional[float] = Field(None, ge=0.01, le=0.30)
    debug: Optional[bool] = None
    max_submit_attempts: Optional[int] = Field(None, ge=1, le=10)
    proxy: Optional[ProxyConfig] = None
    ai_text: Optional[AITextAnswerConfig] = None
    proportion_config: Optional[ProportionConfig] = None


class SubmitResult(BaseModel):
    """单次提交结果"""
    index: int = Field(..., description="提交序号")
    status: Literal["success", "failed"] = Field(..., description="提交状态")
    error: Optional[str] = Field(None, description="错误信息（失败时）")
    proxy_endpoint: Optional[str] = Field(None, description="脱敏代理地址IP:端口")
    proxy_requested_area: Optional[str] = Field(None, description="请求的代理地区")
    proxy_reported_location: Optional[str] = Field(None, description="验证得到的出口地区")
    proxy_exit_ip: Optional[str] = Field(None, description="验证得到的出口IP")
    proxy_carrier: Optional[str] = Field(None, description="代理运营商")
    proxy_remaining_seconds: Optional[int] = Field(None, description="代理提取时剩余秒数")
    proxy_latency_ms: Optional[int] = Field(None, description="出口验证耗时")
    proxy_attempts: int = Field(0, description="代理获取尝试次数")
    failure_stage: Optional[str] = Field(None, description="失败发生阶段")


class TaskStatusResponse(BaseModel):
    """任务状态响应"""
    task_id: str = Field(..., description="任务ID")
    url: Optional[str] = Field(None, description="问卷URL")
    title: Optional[str] = Field(None, description="问卷标题")
    status: Literal["pending", "processing", "completed", "failed", "cancelled"] = Field(..., description="任务状态")
    submitted: int = Field(0, description="已提交成功数")
    failed: int = Field(0, description="失败数")
    total: int = Field(..., description="总数")
    progress: int = Field(0, ge=0, le=100, description="进度百分比")
    remaining: int = 0
    cancel_requested: bool = False
    can_resume: bool = False
    execution_no: int = 0
    resume_count: int = 0
    consecutive_failure_count: int = 0
    max_consecutive_failures: int = 10
    start_time: str = Field(..., description="开始时间")
    end_time: Optional[str] = Field(None, description="结束时间")
    proxy: Optional[ProxyConfig] = Field(None, description="该任务持久化的代理策略")
    ai_text_enabled: bool = Field(False, description="是否启用AI文本题回答")
    ai_text_status: str = Field("disabled", description="答案池生成状态")
    ai_text_generated_count: int = Field(0, description="已预生成的提交份数")
    ai_text_error: Optional[str] = Field(None, description="答案池生成错误")
    proportion_plan_status: str = Field("disabled", description="比例答案计划状态")
    proportion_plan_count: int = Field(0, description="已持久化的比例答案计划数")
    results: List[SubmitResult] = Field(default_factory=list, description="提交结果列表")


# ============================================================================
# 反向题检测相关模型
# ============================================================================

class DetectionQuestion(BaseModel):
    """待检测的题目"""
    id: str = Field(..., description="题目ID", example="q1")
    label: str = Field(..., description="题目文本", example="我对公司的福利待遇很满意")


class DetectionRequest(BaseModel):
    """反向题检测请求"""
    questions: List[DetectionQuestion] = Field(..., description="题目列表", min_items=1)


class DetectionResult(BaseModel):
    """单个题目检测结果"""
    id: str = Field(..., description="题目ID")
    label: str = Field(..., description="题目文本")
    is_reverse: bool = Field(..., description="是否反向题")
    confidence: float = Field(..., description="置信度（0-1）")
    matched_keywords: List[str] = Field(default_factory=list, description="匹配的关键词")


class DetectionResponse(BaseModel):
    """反向题检测响应"""
    total_questions: int = Field(..., description="题目总数")
    reverse_count: int = Field(..., description="反向题数量")
    results: List[DetectionResult] = Field(default_factory=list, description="检测结果列表")


# ============================================================================
# AI 配置相关模型
# ============================================================================

class AIConfigRequest(BaseModel):
    """AI配置请求"""
    api_key: Optional[str] = Field(None, description="OpenAI API密钥")
    model: Optional[str] = Field(None, description="模型名称，如gpt-4o-mini")
    base_url: Optional[str] = Field(None, description="API基础URL（支持自定义代理）")
    enabled: Optional[bool] = Field(None, description="是否启用AI检测")


class AIConfigResponse(BaseModel):
    """AI配置响应"""
    model: str = Field(..., description="当前模型名称")
    base_url: str = Field(..., description="当前API基础URL")
    enabled: bool = Field(..., description="是否启用AI检测")
    has_api_key: bool = Field(..., description="是否已配置API密钥（不返回密钥原文）")


class AITestResponse(BaseModel):
    """AI连通性测试响应"""
    success: bool = Field(..., description="测试是否成功")
    message: str = Field(..., description="测试消息")

