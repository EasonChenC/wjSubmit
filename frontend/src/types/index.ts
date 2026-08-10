export interface User { id:number|string; username:string; email?:string }
export interface Question { id:string; type:string; label:string; options:any[]; required:boolean; is_scale:boolean; is_reverse:boolean; reverse_confidence:number|null; detection_method?:'ai'|'keyword'; positive_values?:any[]; negative_values?:any[]; neutral_values?:any[] }
export interface Questionnaire { task_id:string; activity_id:string; url:string; total_questions:number; question_types:Record<string,number>; questions:Question[]; scale_questions:number; reverse_items:string[] }
export interface SubmitConfig { attitude:'positive'|'negative'; add_variation:boolean; variation_ratio:number }
export interface Task { task_id:string; status:'pending'|'processing'|'completed'|'failed'; submitted:number; failed:number; total:number; progress:number; start_time:string; end_time?:string|null; results?:Array<{index:number;status:'success'|'failed';error?:string}>; url?:string; mode?:string }
