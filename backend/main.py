from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from database import engine, Base, get_db, SessionLocal
import models
from datetime import datetime
from pydantic import BaseModel
from typing import List, Optional
import uuid
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
import pandas as pd
import json
import io
import requests

# Create tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Work Order System API")

# WebSocket Connection Manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(message))
            except Exception:
                pass

manager = ConnectionManager()

# Seed initial data
@app.on_event("startup")
def startup_event():
    db = SessionLocal()
    # Seed Users
    if db.query(models.User).count() == 0:
        db.add_all([
            models.User(name="张三", role=models.RoleEnum.worker, skills="电工"),
            models.User(name="李四", role=models.RoleEnum.worker, skills="水暖"),
            models.User(name="王五", role=models.RoleEnum.worker, skills="木工")
        ])
        db.commit()

    # Seed Materials
    if db.query(models.Material).count() == 0:
        db.add_all([
            models.Material(name="通用螺丝", category="五金", spec="M4*20", unit="包", stock=1000),
            models.Material(name="五类网线", category="弱电", spec="100m", unit="米", stock=5000),
            models.Material(name="绝缘胶带", category="辅材", spec="黑色", unit="卷", stock=200),
            models.Material(name="开关面板", category="强电", spec="单开双控", unit="个", stock=150)
        ])
        db.commit()
    db.close()

os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Pydantic Models ---

class UserBase(BaseModel):
    name: str
    phone: Optional[str] = None
    role: models.RoleEnum = models.RoleEnum.worker
    skills: Optional[str] = None

class UserCreate(UserBase):
    pass

class UserResponse(UserBase):
    id: int
    class Config:
        from_attributes = True

class MaterialBase(BaseModel):
    name: str
    category: Optional[str] = None
    unit: str
    spec: Optional[str] = None
    image_url: Optional[str] = None
    stock: float

class MaterialCreate(MaterialBase):
    pass

class MaterialResponse(MaterialBase):
    id: int
    class Config:
        from_attributes = True

class EvidenceResponse(BaseModel):
    image_url: str
    class Config:
        from_attributes = True

class MaterialItem(BaseModel):
    material_id: int
    quantity: float
    unit: Optional[str] = None

class OrderResponse(BaseModel):
    id: str
    description: str
    status: models.OrderStatusEnum
    created_at: datetime
    accepted_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    worker: Optional[UserResponse] = None
    completer_names: Optional[str] = None
    cancel_history: Optional[str] = None
    evidence: List[EvidenceResponse] = []
    materials: List[MaterialItem] = [] # 返回物料以便移动端查看历史详情
    
    class Config:
        from_attributes = True

class OrderCreate(BaseModel):
    id: Optional[str] = None
    description: str

class CompleteOrderReq(BaseModel):
    image_urls: List[str]
    completer_names: str
    materials: List[MaterialItem] = []

# --- WebSocket ---

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# --- User APIs ---

@app.get("/users/", response_model=List[UserResponse])
def get_users(db: Session = Depends(get_db)):
    return db.query(models.User).all()

@app.post("/users/", response_model=UserResponse)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    db_user = models.User(**user.dict())
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    # 广播通知移动端更新人员库
    import asyncio
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(manager.broadcast({
            "type": "users_updated",
            "message": "人员库已更新"
        }))
    except RuntimeError:
        pass
        
    return db_user

@app.put("/users/{user_id}", response_model=UserResponse)
def update_user(user_id: int, user: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="人员不存在")
    
    db_user.name = user.name
    db_user.phone = user.phone
    db_user.role = user.role
    db_user.skills = user.skills
    
    db.commit()
    db.refresh(db_user)
    
    import asyncio
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(manager.broadcast({
            "type": "users_updated",
            "message": "人员库已更新"
        }))
    except RuntimeError:
        pass
        
    return db_user

@app.delete("/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="人员不存在")
    db.delete(db_user)
    db.commit()
    
    import asyncio
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(manager.broadcast({
            "type": "users_updated",
            "message": "人员库已更新"
        }))
    except RuntimeError:
        pass
        
    return {"message": "删除成功"}

# --- Material APIs ---

@app.get("/materials/", response_model=List[MaterialResponse])
def get_materials(db: Session = Depends(get_db)):
    return db.query(models.Material).all()

@app.post("/materials/", response_model=MaterialResponse)
def create_material(mat: MaterialCreate, db: Session = Depends(get_db)):
    db_mat = models.Material(**mat.dict())
    db.add(db_mat)
    db.commit()
    db.refresh(db_mat)
    return db_mat

@app.put("/materials/{material_id}", response_model=MaterialResponse)
def update_material(material_id: int, mat: MaterialCreate, db: Session = Depends(get_db)):
    db_mat = db.query(models.Material).filter(models.Material.id == material_id).first()
    if not db_mat:
        raise HTTPException(status_code=404, detail="材料不存在")
    
    db_mat.name = mat.name
    db_mat.category = mat.category
    db_mat.unit = mat.unit
    db_mat.spec = mat.spec
    db_mat.image_url = mat.image_url
    db_mat.stock = mat.stock
    
    db.commit()
    db.refresh(db_mat)
    
    # Broadcast material update to mobile clients
    # so they can refresh their dropdowns
    import asyncio
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(manager.broadcast({
            "type": "materials_updated",
            "message": "材料库已更新"
        }))
    except RuntimeError:
        pass # If not running in event loop directly
        
    return db_mat

@app.delete("/materials/{material_id}")
def delete_material(material_id: int, db: Session = Depends(get_db)):
    db_mat = db.query(models.Material).filter(models.Material.id == material_id).first()
    if not db_mat:
        raise HTTPException(status_code=404, detail="材料不存在")
    db.delete(db_mat)
    db.commit()
    
    import asyncio
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(manager.broadcast({
            "type": "materials_updated",
            "message": "材料库已更新"
        }))
    except RuntimeError:
        pass
        
    return {"message": "删除成功"}

@app.post("/materials/import")
async def import_materials(file: UploadFile = File(...), db: Session = Depends(get_db)):
    try:
        content = await file.read()
        import io
        
        # 判断文件扩展名，选择合适的引擎
        filename = file.filename.lower()
        if filename.endswith('.xls'):
            df = pd.read_excel(io.BytesIO(content), engine='xlrd')
        else:
            df = pd.read_excel(io.BytesIO(content), engine='openpyxl')
            
        for _, row in df.iterrows():
            name = str(row.get("名称", ""))
            if not name or name == 'nan':
                continue
                
            category = str(row.get("品类", ""))
            spec = str(row.get("规格", ""))
            unit = str(row.get("单位", ""))
            stock = float(row.get("库存", row.get("现有库存", 0)))
            image_url = str(row.get("图片链接", "")) if pd.notna(row.get("图片链接")) else None
            if image_url == 'nan':
                image_url = None

            # 检查是否已存在同名材料
            existing_mat = db.query(models.Material).filter(models.Material.name == name).first()
            
            if existing_mat:
                # 更新现有材料
                if category and category != 'nan': existing_mat.category = category
                if spec and spec != 'nan': existing_mat.spec = spec
                if unit and unit != 'nan': existing_mat.unit = unit
                existing_mat.stock = stock # 以导入的库存为准，或可做累加 += stock
                if image_url: existing_mat.image_url = image_url
            else:
                # 新增材料
                mat = models.Material(
                    category=category if category != 'nan' else None,
                    name=name,
                    spec=spec if spec != 'nan' else None,
                    unit=unit if unit != 'nan' else "",
                    stock=stock,
                    image_url=image_url
                )
                db.add(mat)
                
        db.commit()
        
        # 广播通知移动端更新
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(manager.broadcast({
                "type": "materials_updated",
                "message": "材料库已更新"
            }))
        except RuntimeError:
            pass
            
        return {"message": "批量导入/更新成功"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"导入失败: {str(e)}")

@app.get("/materials/export")
def export_materials(db: Session = Depends(get_db)):
    materials = db.query(models.Material).all()
    data = [{
        "品类": m.category or "",
        "名称": m.name,
        "规格": m.spec or "",
        "单位": m.unit,
        "现有库存": m.stock,
        "图片链接": m.image_url or ""
    } for m in materials]
    
    df = pd.DataFrame(data)
    os.makedirs("exports", exist_ok=True)
    file_path = f"exports/materials_list_{uuid.uuid4().hex[:6]}.xlsx"
    df.to_excel(file_path, index=False)
    
    return FileResponse(
        file_path, 
        filename="材料清单.xlsx", 
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# --- Order APIs ---

@app.get("/orders/next_id")
def get_next_order_id(db: Session = Depends(get_db)):
    latest = db.query(models.Order).filter(models.Order.id.like("WO-%")).order_by(models.Order.created_at.desc()).first()
    if latest:
        try:
            # Extract number from formats like WO-0001
            parts = latest.id.split("-")
            if len(parts) >= 2:
                # 过滤出字符串中的数字部分，以防有 WO-0001A 这种奇怪的测试数据
                import re
                num_str = re.sub(r'\D', '', parts[1])
                if num_str:
                    num = int(num_str)
                    return {"next_id": f"WO-{num+1:04d}"}
        except Exception:
            pass
    return {"next_id": "WO-0001"}

@app.post("/orders/", response_model=OrderResponse)
async def create_order(order: OrderCreate, db: Session = Depends(get_db)):
    order_id = order.id
    if not order_id:
        # Fallback generate if empty
        res = get_next_order_id(db)
        order_id = res["next_id"]
        
    db_order = models.Order(
        id=order_id,
        description=order.description,
        status=models.OrderStatusEnum.pending,
        created_at=datetime.utcnow()
    )
    db.add(db_order)
    db.commit()
    db.refresh(db_order)
    
    # 广播新工单消息
    await manager.broadcast({
        "type": "new_order",
        "message": f"有新的工单发布: {order_id}",
        "order_id": order_id
    })
    
    return db_order

@app.get("/orders/", response_model=List[OrderResponse])
def get_orders(skip: int = 0, limit: int = 100, status: Optional[models.OrderStatusEnum] = None, db: Session = Depends(get_db)):
    query = db.query(models.Order)
    if status:
        query = query.filter(models.Order.status == status)
    # Order by created_at descending
    orders = query.order_by(models.Order.created_at.desc()).offset(skip).limit(limit).all()
    return orders

@app.put("/orders/{order_id}/claim", response_model=OrderResponse)
def claim_order(order_id: str, worker_id: int = 1, db: Session = Depends(get_db)):
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="工单不存在")
    if order.status != models.OrderStatusEnum.pending:
        raise HTTPException(status_code=400, detail="工单已被领取或无法领取")
    
    order.status = models.OrderStatusEnum.in_progress
    order.accepted_at = datetime.utcnow()
    order.worker_id = worker_id
    db.commit()
    db.refresh(order)
    return order

@app.put("/orders/{order_id}/cancel", response_model=OrderResponse)
def cancel_order(order_id: str, worker_id: int = 1, db: Session = Depends(get_db)):
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="工单不存在")
    if order.status != models.OrderStatusEnum.in_progress:
        raise HTTPException(status_code=400, detail="只能取消进行中的工单")
    
    worker = db.query(models.User).filter(models.User.id == worker_id).first()
    worker_name = worker.name if worker else f"User_{worker_id}"
    
    cancel_time_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    history_entry = f"{worker_name} 于 {cancel_time_str} 取消;"
    
    order.cancel_history = (order.cancel_history or "") + history_entry
    order.status = models.OrderStatusEnum.pending
    order.worker_id = None
    order.accepted_at = None
    
    db.commit()
    db.refresh(order)
    
    # 广播工单被退回的消息
    import asyncio
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(manager.broadcast({
            "type": "new_order", # 可以复用 new_order 让前端刷新任务大厅
            "message": f"工单 {order_id} 已被退回任务大厅",
            "order_id": order_id
        }))
    except RuntimeError:
        pass
        
    return order

@app.put("/orders/{order_id}/complete", response_model=OrderResponse)
def complete_order(order_id: str, req: CompleteOrderReq, db: Session = Depends(get_db)):
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="工单不存在")
    if order.status != models.OrderStatusEnum.in_progress:
        raise HTTPException(status_code=400, detail="只能完工进行中的工单")
        
    order.status = models.OrderStatusEnum.review
    order.completed_at = datetime.utcnow()
    order.completer_names = req.completer_names
    
    # 记录完工证明(多张)
    for img_url in req.image_urls:
        evidence = models.Evidence(
            order_id=order_id,
            image_url=img_url,
            uploaded_at=datetime.utcnow()
        )
        db.add(evidence)
    
    # 记录物料消耗
    for mat in req.materials:
        om = models.OrderMaterial(
            order_id=order_id,
            material_id=mat.material_id,
            quantity=mat.quantity,
            unit=mat.unit
        )
        db.add(om)
        # 扣减库存
        db_mat = db.query(models.Material).filter(models.Material.id == mat.material_id).first()
        if db_mat:
            db_mat.stock -= mat.quantity

    db.commit()
    db.refresh(order)
    return order

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    # 模拟上传到 OSS，实际保存到本地 uploads 文件夹
    file_ext = file.filename.split(".")[-1]
    new_filename = f"{uuid.uuid4().hex}.{file_ext}"
    file_location = f"uploads/{new_filename}"
    
    with open(file_location, "wb+") as file_object:
        file_object.write(file.file.read())
        
    # 返回可供访问的图片 URL
    return {"url": f"http://39.108.124.19:8000/uploads/{new_filename}"}

@app.get("/orders/export")
def export_orders(start_date: Optional[str] = None, end_date: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(models.Order)
    if start_date:
        query = query.filter(models.Order.created_at >= datetime.strptime(start_date, "%Y-%m-%d"))
    if end_date:
        query = query.filter(models.Order.created_at <= datetime.strptime(end_date, "%Y-%m-%d"))
    
    orders = query.order_by(models.Order.created_at.desc()).all()
    
    data = []
    image_data = [] # Store image URLs separately to process them
    
    for idx, o in enumerate(orders):
        mats = [f"{m.material.name}({m.quantity}{m.unit or m.material.unit})" for m in o.materials]
        imgs = [e.image_url for e in o.evidence]
        
        row_data = {
            "工单号": o.id,
            "工单描述": o.description,
            "状态": o.status.value,
            "创建时间": o.created_at.strftime("%Y-%m-%d %H:%M:%S") if o.created_at else "",
            "领取时间": o.accepted_at.strftime("%Y-%m-%d %H:%M:%S") if o.accepted_at else "",
            "完工时间": o.completed_at.strftime("%Y-%m-%d %H:%M:%S") if o.completed_at else "",
            "领单技工": o.worker.name if o.worker else "",
            "完工人员": o.completer_names or "",
            "消耗物料": "; ".join(mats),
            "完工照片": "" # Leave blank in dataframe, we will insert images here
        }
        data.append(row_data)
        image_data.append(imgs)
        
    df = pd.DataFrame(data)
    os.makedirs("exports", exist_ok=True)
    file_path = f"exports/orders_report_{uuid.uuid4().hex[:6]}.xlsx"
    
    # Use xlsxwriter engine to support image insertion
    writer = pd.ExcelWriter(file_path, engine='xlsxwriter')
    df.to_excel(writer, index=False, sheet_name='Sheet1')
    
    workbook = writer.book
    worksheet = writer.sheets['Sheet1']
    
    # Adjust column width and row height for images
    worksheet.set_column('J:J', 60) # 增加完工照片列宽以容纳多图
    
    # Insert images
    import PIL.Image as PILImage
    
    for row_idx, imgs in enumerate(image_data):
        if not imgs:
            continue
            
        worksheet.set_row(row_idx + 1, 100) # 显著增加行高以适应图片
        
        # Calculate x offset to put multiple images side by side in the same cell
        x_offset = 5
        for img_url in imgs:
            try:
                if "uploads/" in img_url:
                    filename = img_url.split("uploads/")[-1]
                    local_path = os.path.join("uploads", filename)
                    if os.path.exists(local_path):
                        # 动态计算缩放比例
                        with PILImage.open(local_path) as img:
                            width, height = img.size
                            
                        # 目标最大高度和宽度（像素）
                        target_height = 120.0
                        target_width = 120.0
                        
                        scale_y = target_height / height
                        scale_x = target_width / width
                        
                        # 保持宽高比，取较小的缩放率
                        scale = min(scale_x, scale_y)
                        
                        worksheet.insert_image(row_idx + 1, 9, local_path, 
                                            {'x_scale': scale, 'y_scale': scale, 'x_offset': x_offset, 'y_offset': 5, 'positioning': 1})
                        
                        # 下一张图片向右偏移 (计算实际缩放后的宽度 + 间距)
                        actual_width = width * scale
                        x_offset += int(actual_width) + 10 
            except Exception as e:
                print(f"Error inserting image: {e}")
                pass
                
    writer.close()
    
    return FileResponse(
        file_path, 
        filename="工单数据报表.xlsx", 
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

@app.get("/reports/export")
def export_report(db: Session = Depends(get_db)):
    records = db.query(models.OrderMaterial, models.Order, models.Material)\
        .join(models.Order, models.Order.id == models.OrderMaterial.order_id)\
        .join(models.Material, models.Material.id == models.OrderMaterial.material_id).all()
    
    data = []
    for om, o, m in records:
        data.append({
            "工单号": o.id,
            "工单描述": o.description,
            "物料名称": m.name,
            "消耗数量": om.quantity,
            "单位": om.unit or m.unit,
            "完工时间": o.completed_at.strftime("%Y-%m-%d %H:%M:%S") if o.completed_at else ""
        })
    
    if not data:
        raise HTTPException(status_code=404, detail="暂无物料消耗数据")

    df = pd.DataFrame(data)
    os.makedirs("exports", exist_ok=True)
    file_path = f"exports/material_report_{uuid.uuid4().hex[:6]}.xlsx"
    df.to_excel(file_path, index=False)
    
    return FileResponse(
        file_path, 
        filename="物料消耗报表.xlsx", 
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
