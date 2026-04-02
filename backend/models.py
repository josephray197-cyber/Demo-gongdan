from sqlalchemy import Column, Integer, String, Enum, DateTime, ForeignKey, Float
from sqlalchemy.orm import relationship
import enum
from database import Base

class RoleEnum(str, enum.Enum):
    admin = "admin"
    worker = "worker"

class OrderStatusEnum(str, enum.Enum):
    pending = "pending"          # 待指派/待领取
    in_progress = "in_progress"  # 已领取
    review = "review"            # 待验收
    completed = "completed"      # 已完成

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    role = Column(Enum(RoleEnum), default=RoleEnum.worker)
    name = Column(String, index=True)
    phone = Column(String, nullable=True) # 联系电话
    skills = Column(String)

    orders = relationship("Order", back_populates="worker", foreign_keys="[Order.worker_id]")

class Order(Base):
    __tablename__ = "orders"
    id = Column(String, primary_key=True, index=True) # 工单号
    description = Column(String)
    status = Column(Enum(OrderStatusEnum), default=OrderStatusEnum.pending)
    created_at = Column(DateTime)
    accepted_at = Column(DateTime, nullable=True) # 领取时间
    completed_at = Column(DateTime, nullable=True) # 完成时间
    worker_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    completer_names = Column(String, nullable=True) # 完工人员名称，逗号分隔
    cancel_history = Column(String, nullable=True) # 记录取消轨迹，例如 "张三 取消于 2023-01-01;"

    worker = relationship("User", foreign_keys=[worker_id], back_populates="orders")
    materials = relationship("OrderMaterial", back_populates="order")
    evidence = relationship("Evidence", back_populates="order")

class Material(Base):
    __tablename__ = "materials"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    category = Column(String, nullable=True) # 品类
    unit = Column(String)
    spec = Column(String, nullable=True) # 规格
    image_url = Column(String, nullable=True) # 图片
    stock = Column(Float, default=0.0)

class OrderMaterial(Base):
    __tablename__ = "order_materials"
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(String, ForeignKey("orders.id"))
    material_id = Column(Integer, ForeignKey("materials.id"))
    quantity = Column(Float)
    unit = Column(String, nullable=True) # 手动修改的单位

    order = relationship("Order", back_populates="materials")
    material = relationship("Material")

class Evidence(Base):
    __tablename__ = "evidence"
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(String, ForeignKey("orders.id"))
    image_url = Column(String)
    uploaded_at = Column(DateTime)
    location = Column(String, nullable=True)

    order = relationship("Order", back_populates="evidence")