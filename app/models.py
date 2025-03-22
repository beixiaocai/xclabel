from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    username = db.Column(db.String(100), nullable=False)
    sort = db.Column(db.Integer, nullable=False)
    code = db.Column(db.String(50), nullable=False, unique=True)
    name = db.Column(db.String(50), nullable=False)
    task_type = db.Column(db.Integer, nullable=False)  # 1:图片 2:视频 3:音频
    remark = db.Column(db.Text, nullable=True)
    sample_annotation_count = db.Column(db.Integer, nullable=False)
    sample_count = db.Column(db.Integer, nullable=False)
    labels = db.Column(db.Text, nullable=True)
    create_time = db.Column(db.DateTime, default=datetime.utcnow)
    create_timestamp = db.Column(db.Integer, nullable=False)
    last_update_time = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    state = db.Column(db.Integer, nullable=False)

    def __repr__(self):
        return f'<Task {self.name}>'

class TaskSample(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sort = db.Column(db.Integer, nullable=False)
    code = db.Column(db.String(50), nullable=False, unique=True)
    user_id = db.Column(db.Integer, nullable=False)
    username = db.Column(db.String(100), nullable=False)
    task_type = db.Column(db.Integer, nullable=False)
    task_code = db.Column(db.String(50), nullable=False)
    old_filename = db.Column(db.String(200), nullable=False)
    new_filename = db.Column(db.String(200), nullable=False)
    remark = db.Column(db.String(100), nullable=True)
    create_time = db.Column(db.DateTime, default=datetime.utcnow)
    state = db.Column(db.Integer, nullable=False)  # 0:样本所属任务不存在 1:样本所属任务存在 默认0
    annotation_user_id = db.Column(db.Integer, nullable=False)
    annotation_username = db.Column(db.String(100), nullable=False)
    annotation_time = db.Column(db.DateTime, nullable=True)
    annotation_content = db.Column(db.Text, nullable=True)
    annotation_state = db.Column(db.Integer, nullable=False)  # 0:未标注 1:已标注 默认0

    def __repr__(self):
        return f'<TaskSample {self.code}>'

class TaskTrain(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sort = db.Column(db.Integer, nullable=False)
    code = db.Column(db.String(50), nullable=False, unique=True)
    user_id = db.Column(db.Integer, nullable=False)
    username = db.Column(db.String(100), nullable=False)
    task_code = db.Column(db.String(50), nullable=False)
    algorithm_code = db.Column(db.String(50), nullable=False)
    device = db.Column(db.String(50), nullable=False)
    imgsz = db.Column(db.Integer, nullable=False)
    epochs = db.Column(db.Integer, nullable=False)
    batch = db.Column(db.Integer, nullable=False)
    save_period = db.Column(db.Integer, nullable=False)
    sample_ratio = db.Column(db.Integer, nullable=False)
    extra = db.Column(db.Text, nullable=True)
    create_time = db.Column(db.DateTime, default=datetime.utcnow)
    train_datasets = db.Column(db.String(200), nullable=True)
    train_datasets_remark = db.Column(db.String(200), nullable=True)
    train_datasets_time = db.Column(db.DateTime, nullable=True)
    train_command = db.Column(db.String(200), nullable=True)
    train_process_name = db.Column(db.String(100), nullable=True)
    train_pid = db.Column(db.Integer, nullable=True)
    train_count = db.Column(db.Integer, nullable=False)
    train_state = db.Column(db.Integer, nullable=False)  # 0:未开启训练 1:训练中 2:已完成
    train_start_time = db.Column(db.DateTime, nullable=True)
    train_stop_time = db.Column(db.DateTime, nullable=True)
    train_remark = db.Column(db.String(200), nullable=True)

    def __repr__(self):
        return f'<TaskTrain {self.code}>'

class TaskTrainTest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sort = db.Column(db.Integer, nullable=False)
    code = db.Column(db.String(50), nullable=False, unique=True)
    user_id = db.Column(db.Integer, nullable=False)
    username = db.Column(db.String(100), nullable=False)
    task_code = db.Column(db.String(50), nullable=False)
    train_code = db.Column(db.String(50), nullable=False)
    file_name = db.Column(db.String(100), nullable=False)
    file_size = db.Column(db.Integer, nullable=False)
    file_type = db.Column(db.Integer, nullable=False)  # 0:未知 1:图片 2:视频
    calcu_seconds = db.Column(db.Float, nullable=False)  # 计算耗时
    create_time = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<TaskTrainTest {self.code}>'
