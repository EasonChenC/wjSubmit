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
    detection_method: str = Field("keyword", description="使用的检测方法（keyword 或 ai）")


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


class SubmitRequest(BaseModel):
    """问卷提交请求

    task_id 对应 analyze_questionnaire 返回的任务ID。提交时直接读取该任务
    落库的 analyzed_schema 生成答案，不会重新访问问卷页面或重新分析。
    """
    task_id: str = Field(..., description="任务ID（由 /analyze 接口返回）")
    count: int = Field(..., ge=1, le=1000, description="提交份数（1-1000）")
    mode: Literal["random", "high_reliability"] = Field(
        ...,
        description="提交模式：random(随机) 或 high_reliability(高信度)"
    )
    config: Optional[SubmitConfig] = Field(
        None,
        description="模式配置（mode为high_reliability时必填）"
    )

    @validator('config')
    def validate_config(cls, v, values):
        """验证config字段"""
        mode = values.get('mode')
        if mode == 'high_reliability' and v is None:
            raise ValueError('high_reliability模式必须提供config配置')
        return v


class SubmitResult(BaseModel):
    """单次提交结果"""
    index: int = Field(..., description="提交序号")
    status: Literal["success", "failed"] = Field(..., description="提交状态")
    error: Optional[str] = Field(None, description="错误信息（失败时）")


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
    start_time: str = Field(..., description="开始时间")
    end_time: Optional[str] = Field(None, description="结束时间")
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

