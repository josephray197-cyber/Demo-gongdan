<script setup lang="ts">
import { ref, onMounted } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { Download, Plus, Refresh, ArrowDown, Warning } from '@element-plus/icons-vue'

const apiBaseUrl = 'http://39.108.124.19:8000'
const activeTab = ref('orders')

// ---- 工单管理 ----
interface Order {
  id: string
  description: string
  status: string
  created_at: string
  accepted_at?: string
  completed_at?: string
  worker?: { name: string }
  completer_names?: string
  cancel_history?: string
  evidence?: { image_url: string }[]
}

const orders = ref<Order[]>([])
const orderDialogVisible = ref(false)
const newOrderForm = ref({ id: '', description: '' })
const exportOrderDialogVisible = ref(false)
const exportDateRange = ref<[Date, Date] | null>(null)

const fetchOrders = async () => {
  try {
    const response = await axios.get(`${apiBaseUrl}/orders/`)
    orders.value = response.data
  } catch (error) {
    ElMessage.error('获取工单列表失败')
  }
}

const openOrderDialog = async () => {
  try {
    const res = await axios.get(`${apiBaseUrl}/orders/next_id`)
    newOrderForm.value.id = res.data.next_id
    newOrderForm.value.description = ''
    orderDialogVisible.value = true
  } catch (e) {
    ElMessage.error('获取新工单号失败')
  }
}

const createOrder = async () => {
  if (!newOrderForm.value.description) {
    ElMessage.warning('请输入工单描述')
    return
  }
  if (!newOrderForm.value.id) {
    ElMessage.warning('请输入工单号')
    return
  }
  try {
    await axios.post(`${apiBaseUrl}/orders/`, newOrderForm.value)
    ElMessage.success('工单发布成功')
    orderDialogVisible.value = false
    fetchOrders()
  } catch (error) {
    ElMessage.error('工单发布失败: 工单号可能已存在')
  }
}

const getStatusType = (status: string) => {
  const map: Record<string, string> = { pending: 'info', in_progress: 'primary', review: 'warning', completed: 'success' }
  return map[status] || 'info'
}

const getStatusLabel = (status: string) => {
  const map: Record<string, string> = { pending: '待指派', in_progress: '已领取', review: '待验收', completed: '已完成' }
  return map[status] || status
}

const exportOrderReport = () => {
  exportOrderDialogVisible.value = true
}

const doExportOrders = () => {
  let url = `${apiBaseUrl}/orders/export`
  if (exportDateRange.value && exportDateRange.value.length === 2) {
    const start = exportDateRange.value[0].toISOString().split('T')[0]
    const end = exportDateRange.value[1].toISOString().split('T')[0]
    url += `?start_date=${start}&end_date=${end}`
  }
  window.open(url, '_blank')
  exportOrderDialogVisible.value = false
}

const exportMaterialReport = () => {
  window.open(`${apiBaseUrl}/reports/export`, '_blank')
}

// ---- 材料清单 ----
const materials = ref<any[]>([])
const matDialogVisible = ref(false)
const matForm = ref({ id: null as number | null, name: '', category: '', unit: '', spec: '', stock: 0, image_url: '' })
const isEditingMat = ref(false)

const fetchMaterials = async () => {
  try {
    const res = await axios.get(`${apiBaseUrl}/materials/`)
    materials.value = res.data
  } catch (e) {
    ElMessage.error('获取材料列表失败')
  }
}

const openMatDialog = () => {
  isEditingMat.value = false
  matForm.value = { id: null, name: '', category: '', unit: '', spec: '', stock: 0, image_url: '' }
  matDialogVisible.value = true
}

const editMaterial = (row: any) => {
  isEditingMat.value = true
  matForm.value = { ...row }
  matDialogVisible.value = true
}

const handleMaterialImageSuccess = (response: any) => {
  if (response && response.url) {
    matForm.value.image_url = response.url
    ElMessage.success('图片上传成功')
  }
}

const deleteMaterial = async (id: number) => {
  if (!confirm('确定要删除这个材料吗？')) return
  try {
    await axios.delete(`${apiBaseUrl}/materials/${id}`)
    ElMessage.success('删除成功')
    fetchMaterials()
  } catch (e) {
    ElMessage.error('删除失败')
  }
}

const saveMaterial = async () => {
  try {
    if (isEditingMat.value && matForm.value.id) {
      await axios.put(`${apiBaseUrl}/materials/${matForm.value.id}`, matForm.value)
      ElMessage.success('更新材料成功')
    } else {
      await axios.post(`${apiBaseUrl}/materials/`, matForm.value)
      ElMessage.success('添加材料成功')
    }
    matDialogVisible.value = false
    fetchMaterials()
  } catch (e) {
    ElMessage.error('保存失败')
  }
}

const exportMaterials = () => {
  window.open(`${apiBaseUrl}/materials/export`, '_blank')
}

// ---- 人员库 ----
const users = ref<any[]>([])
const userDialogVisible = ref(false)
const userForm = ref({ id: null as number | null, name: '', phone: '', skills: '', role: 'worker' })
const isEditingUser = ref(false)

const fetchUsers = async () => {
  try {
    const res = await axios.get(`${apiBaseUrl}/users/`)
    users.value = res.data
  } catch (e) {
    ElMessage.error('获取人员列表失败')
  }
}

const openUserDialog = () => {
  isEditingUser.value = false
  userForm.value = { id: null, name: '', phone: '', skills: '', role: 'worker' }
  userDialogVisible.value = true
}

const editUser = (row: any) => {
  isEditingUser.value = true
  userForm.value = { ...row }
  userDialogVisible.value = true
}

const deleteUser = async (id: number) => {
  if (!confirm('确定要删除该人员吗？相关的工单历史记录将受影响。')) return
  try {
    await axios.delete(`${apiBaseUrl}/users/${id}`)
    ElMessage.success('删除成功')
    fetchUsers()
  } catch (e) {
    ElMessage.error('删除失败')
  }
}

const saveUser = async () => {
  if (!userForm.value.name) {
    ElMessage.warning('请输入姓名')
    return
  }
  try {
    if (isEditingUser.value && userForm.value.id) {
      await axios.put(`${apiBaseUrl}/users/${userForm.value.id}`, userForm.value)
      ElMessage.success('更新人员成功')
    } else {
      await axios.post(`${apiBaseUrl}/users/`, userForm.value)
      ElMessage.success('添加人员成功')
    }
    userDialogVisible.value = false
    fetchUsers()
  } catch (e) {
    ElMessage.error('保存失败')
  }
}

onMounted(() => {
  fetchOrders()
  fetchMaterials()
  fetchUsers()
})
</script>

<template>
  <div class="app-container">
    <el-container>
      <el-header class="header">
        <h2>轻量级工单处理系统 - 管理后台</h2>
      </el-header>
      
      <el-main>
        <el-tabs v-model="activeTab" type="border-card">
          <!-- 工单管理 Tab -->
          <el-tab-pane label="工单管理" name="orders">
            <div class="toolbar">
              <el-button type="primary" @click="openOrderDialog">
                <el-icon><Plus /></el-icon> 发布工单
              </el-button>
              <el-button @click="fetchOrders">
                <el-icon><Refresh /></el-icon> 刷新
              </el-button>
              <el-button type="success" @click="exportOrderReport" style="margin-left: auto;">
                <el-icon><Download /></el-icon> 导出工单数据
              </el-button>
              <el-button type="warning" @click="exportMaterialReport">
                <el-icon><Download /></el-icon> 导出物料消耗报表
              </el-button>
            </div>

            <el-table :data="orders" style="width: 100%" border stripe>
              <el-table-column prop="id" label="工单号" width="120" />
              <el-table-column prop="description" label="工单描述" min-width="150" />
              <el-table-column prop="status" label="状态" width="100">
                <template #default="{ row }">
                  <el-tag :type="getStatusType(row.status)">{{ getStatusLabel(row.status) }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="领单技工" width="100">
                <template #default="{ row }">
                  {{ row.worker?.name || '-' }}
                  <el-tooltip v-if="row.cancel_history" effect="dark" :content="row.cancel_history" placement="top">
                    <el-icon style="color: #f56c6c; margin-left: 5px; cursor: pointer;"><Warning /></el-icon>
                  </el-tooltip>
                </template>
              </el-table-column>
              <el-table-column label="完工技工" width="120">
                <template #default="{ row }">{{ row.completer_names || '-' }}</template>
              </el-table-column>
              <el-table-column label="时效与时间" width="200">
                <template #default="{ row }">
                  <div style="font-size: 12px; color: #666;">创建: {{ new Date(row.created_at).toLocaleString() }}</div>
                  <div v-if="row.completed_at" style="font-size: 12px; color: #67C23A;">
                    完工: {{ new Date(row.completed_at).toLocaleString() }}
                  </div>
                  <div v-if="row.completed_at && row.accepted_at" style="color: #67C23A; font-weight: bold; margin-top: 4px;">
                    耗时: {{ Math.round((new Date(row.completed_at).getTime() - new Date(row.accepted_at).getTime()) / 60000) }} 分钟
                  </div>
                  <div v-else-if="row.accepted_at" style="color: #E6A23C; margin-top: 4px;">
                    处理中: {{ Math.round((new Date().getTime() - new Date(row.accepted_at).getTime()) / 60000) }} 分钟
                  </div>
                </template>
              </el-table-column>
              <el-table-column label="完工照片" width="200" align="center">
                <template #default="{ row }">
                  <div v-if="row.evidence && row.evidence.length > 0" style="display: flex; gap: 5px; flex-wrap: wrap; justify-content: center;">
                    <el-image 
                      v-for="(img, idx) in row.evidence"
                      :key="idx"
                      :src="img.image_url" 
                      :preview-src-list="row.evidence.map((e: any) => e.image_url)"
                      :initial-index="idx"
                      fit="cover"
                      style="width: 50px; height: 50px; border-radius: 4px;"
                      preview-teleported
                    />
                  </div>
                  <span v-else style="color: #ccc; font-size: 12px;">无</span>
                </template>
              </el-table-column>
            </el-table>
          </el-tab-pane>

          <!-- 材料清单 Tab -->
          <el-tab-pane label="材料清单" name="materials">
            <div class="toolbar">
              <el-button type="primary" @click="openMatDialog">
                <el-icon><Plus /></el-icon> 新增材料
              </el-button>
              
              <el-dropdown trigger="click" style="margin-right: 10px;">
                <el-button type="warning">
                  批量导入 <el-icon class="el-icon--right"><arrow-down /></el-icon>
                </el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item>
                      <el-upload
                        :action="`${apiBaseUrl}/materials/import`"
                        :show-file-list="false"
                        accept=".xls,.xlsx"
                        :on-success="() => { ElMessage.success('批量导入成功'); fetchMaterials(); }"
                        :on-error="() => ElMessage.error('批量导入失败')"
                        style="display: inline-block; width: 100%; text-align: left;"
                      >
                        上传文件
                      </el-upload>
                    </el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>

              <el-button @click="fetchMaterials">
                <el-icon><Refresh /></el-icon> 刷新
              </el-button>
              <el-button type="success" @click="exportMaterials" style="margin-left: auto;">
                <el-icon><Download /></el-icon> 导出材料清单
              </el-button>
            </div>
            <el-table :data="materials" style="width: 100%" border stripe>
              <el-table-column prop="category" label="品类" width="120" />
              <el-table-column prop="name" label="材料名称" />
              <el-table-column prop="spec" label="规格" width="120" />
              <el-table-column prop="unit" label="单位" width="80" />
              <el-table-column prop="stock" label="现有库存" width="100">
                <template #default="{ row }">
                  <span :style="{ color: row.stock < 100 ? 'red' : 'inherit', fontWeight: 'bold' }">{{ row.stock }}</span>
                </template>
              </el-table-column>
              <el-table-column label="图片" width="100" align="center">
                <template #default="{ row }">
                  <el-image v-if="row.image_url" :src="row.image_url" style="width: 40px; height: 40px" />
                  <span v-else style="color: #ccc; font-size: 12px;">无</span>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="150" align="center">
                <template #default="{ row }">
                  <el-button size="small" type="primary" link @click="editMaterial(row)">编辑</el-button>
                  <el-button size="small" type="danger" link @click="deleteMaterial(row.id)">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
          </el-tab-pane>

          <!-- 人员库 Tab -->
          <el-tab-pane label="人员库" name="users">
            <div class="toolbar">
              <el-button type="primary" @click="openUserDialog">
                <el-icon><Plus /></el-icon> 新增人员
              </el-button>
              <el-button @click="fetchUsers">
                <el-icon><Refresh /></el-icon> 刷新
              </el-button>
            </div>
            <el-table :data="users" style="width: 100%" border stripe>
              <el-table-column prop="id" label="ID" width="80" />
              <el-table-column prop="name" label="姓名" width="120" />
              <el-table-column prop="phone" label="联系电话" width="150">
                <template #default="{ row }">{{ row.phone || '-' }}</template>
              </el-table-column>
              <el-table-column prop="skills" label="技能/备注" />
              <el-table-column prop="role" label="角色" width="120">
                <template #default="{ row }">
                  <el-tag :type="row.role === 'admin' ? 'danger' : 'info'">{{ row.role === 'admin' ? '管理员' : '技工' }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="150" align="center">
                <template #default="{ row }">
                  <el-button size="small" type="primary" link @click="editUser(row)">编辑</el-button>
                  <el-button size="small" type="danger" link @click="deleteUser(row.id)">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
          </el-tab-pane>
        </el-tabs>
      </el-main>
    </el-container>

    <!-- 发布工单弹窗 -->
    <el-dialog v-model="orderDialogVisible" title="发布新工单" width="500px">
      <el-form :model="newOrderForm" label-width="80px">
        <el-form-item label="工单号" required>
          <el-input v-model="newOrderForm.id" placeholder="可手动修改，默认为自增" />
        </el-form-item>
        <el-form-item label="工单描述" required>
          <el-input v-model="newOrderForm.description" type="textarea" :rows="4" placeholder="请输入维修任务、位置等详细描述..." />
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="orderDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="createOrder">确认发布</el-button>
        </span>
      </template>
    </el-dialog>

    <!-- 新增/编辑材料弹窗 -->
    <el-dialog v-model="matDialogVisible" :title="isEditingMat ? '编辑材料' : '新增材料'" width="500px">
      <el-form :model="matForm" label-width="80px">
        <el-form-item label="品类"><el-input v-model="matForm.category" /></el-form-item>
        <el-form-item label="名称" required><el-input v-model="matForm.name" /></el-form-item>
        <el-form-item label="规格"><el-input v-model="matForm.spec" /></el-form-item>
        <el-form-item label="单位" required><el-input v-model="matForm.unit" /></el-form-item>
        <el-form-item label="现有库存"><el-input-number v-model="matForm.stock" :min="0" /></el-form-item>
        <el-form-item label="图片">
          <el-upload
            class="avatar-uploader"
            :action="`${apiBaseUrl}/upload`"
            :show-file-list="false"
            :on-success="handleMaterialImageSuccess"
            :on-error="() => ElMessage.error('图片上传失败')"
            accept="image/*"
          >
            <img v-if="matForm.image_url" :src="matForm.image_url" class="avatar" />
            <el-icon v-else class="avatar-uploader-icon"><Plus /></el-icon>
          </el-upload>
          <div style="font-size: 12px; color: #999; line-height: 1.2; margin-top: 5px;">
            也可直接输入外部链接:
            <el-input v-model="matForm.image_url" placeholder="可选图片URL" size="small" style="margin-top: 5px;" />
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="matDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="saveMaterial">保存</el-button>
        </span>
      </template>
    </el-dialog>

    <!-- 新增/编辑人员弹窗 -->
    <el-dialog v-model="userDialogVisible" :title="isEditingUser ? '编辑人员' : '新增人员'" width="400px">
      <el-form :model="userForm" label-width="80px">
        <el-form-item label="姓名" required><el-input v-model="userForm.name" /></el-form-item>
        <el-form-item label="联系电话"><el-input v-model="userForm.phone" placeholder="可选" /></el-form-item>
        <el-form-item label="技能/备注"><el-input v-model="userForm.skills" /></el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="userDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="saveUser">保存</el-button>
        </span>
      </template>
    </el-dialog>

    <!-- 导出工单弹窗 -->
    <el-dialog v-model="exportOrderDialogVisible" title="按时间导出工单数据" width="500px">
      <el-form label-width="100px">
        <el-form-item label="选择时间范围">
          <el-date-picker
            v-model="exportDateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            style="width: 100%"
          />
        </el-form-item>
        <div style="font-size: 12px; color: #999; margin-left: 100px;">如果不选时间，将默认导出所有记录。</div>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="exportOrderDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="doExportOrders">导出 Excel</el-button>
        </span>
      </template>
    </el-dialog>

  </div>
</template>

<style scoped>
.app-container {
  min-height: 100vh;
  background-color: #f5f7fa;
}
.header {
  background-color: #409EFF;
  color: white;
  display: flex;
  align-items: center;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}
.header h2 {
  margin: 0;
  font-size: 20px;
}
.toolbar {
  margin-bottom: 15px;
  display: flex;
  gap: 10px;
}
.el-main {
  padding: 20px;
  margin: 0 auto;
  max-width: 1400px;
}

.avatar-uploader .el-upload {
  border: 1px dashed #d9d9d9;
  border-radius: 6px;
  cursor: pointer;
  position: relative;
  overflow: hidden;
  transition: var(--el-transition-duration-fast);
}

.avatar-uploader .el-upload:hover {
  border-color: var(--el-color-primary);
}

.avatar-uploader-icon {
  font-size: 28px;
  color: #8c939d;
  width: 100px;
  height: 100px;
  text-align: center;
  line-height: 100px;
  border: 1px dashed #d9d9d9;
  border-radius: 6px;
}
.avatar-uploader-icon:hover {
  border-color: #409EFF;
}

.avatar {
  width: 100px;
  height: 100px;
  display: block;
  object-fit: cover;
  border-radius: 6px;
}
</style>
