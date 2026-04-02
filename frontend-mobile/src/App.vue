<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import axios from 'axios'
import { showToast, showSuccessToast, showFailToast, showNotify, showImagePreview } from 'vant'

const apiBaseUrl = 'http://39.108.124.19:8000'
const wsBaseUrl = 'ws://39.108.124.19:8000/ws'
const activeTab = ref(0)
const pendingOrders = ref<any[]>([])
const myOrders = ref<any[]>([])
const materials = ref<any[]>([])
const users = ref<any[]>([])
const orderMaterialsMap = ref<any>({})
const completers = ref<any>({})
let ws: WebSocket | null = null

const initWebSocket = () => {
  ws = new WebSocket(wsBaseUrl)
  ws.onopen = () => console.log('WebSocket connected')
  ws.onmessage = (event) => {
    const data = JSON.parse(event.data)
    if (data.type === 'new_order') {
      showNotify({ type: 'success', message: data.message, duration: 3000 })
      fetchPendingOrders()
    } else if (data.type === 'materials_updated') {
      // 收到材料库更新通知，静默刷新本地材料列表
      fetchMaterials()
    } else if (data.type === 'users_updated') {
      // 收到人员库更新通知，静默刷新本地人员列表
      fetchUsers()
    }
  }
  ws.onclose = () => setTimeout(initWebSocket, 3000)
}

const fetchMaterials = async () => {
  try {
    const res = await axios.get(`${apiBaseUrl}/materials/`)
    materials.value = res.data
  } catch (e) {
    showFailToast('获取物料列表失败')
  }
}

const fetchUsers = async () => {
  try {
    const res = await axios.get(`${apiBaseUrl}/users/`)
    // SQLite reset cleared previous test data, let's just use all users for now or check role
    users.value = res.data.filter((u: any) => u.role === 'worker' || u.role === 'admin')
  } catch (e) {
    showFailToast('获取人员列表失败')
  }
}

const fetchPendingOrders = async () => {
  try {
    const res = await axios.get(`${apiBaseUrl}/orders/?status=pending`)
    pendingOrders.value = res.data
  } catch (e) {
    showFailToast('获取工单失败')
  }
}

const fetchMyOrders = async () => {
  try {
    const res1 = await axios.get(`${apiBaseUrl}/orders/?status=in_progress`)
    const res2 = await axios.get(`${apiBaseUrl}/orders/?status=review`)
    const res3 = await axios.get(`${apiBaseUrl}/orders/?status=completed`)
    const combined = [...res1.data, ...res2.data, ...res3.data]
    // 按照创建时间/领取时间先后顺序排列
    combined.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    myOrders.value = combined
  } catch (e) {
    showFailToast('获取我的工单失败')
  }
}

const claimOrder = async (orderId: string) => {
  try {
    // 默认技工ID为1，实际可做登录鉴权
    await axios.put(`${apiBaseUrl}/orders/${orderId}/claim?worker_id=1`)
    showSuccessToast('领单成功')
    fetchPendingOrders()
    fetchMyOrders()
  } catch (e) {
    showFailToast('领单失败')
  }
}

import { showConfirmDialog } from 'vant'

const cancelOrder = (orderId: string) => {
  showConfirmDialog({
    title: '确认取消',
    message: '取消后该工单将退回任务大厅，确定要取消吗？',
  }).then(async () => {
    try {
      await axios.put(`${apiBaseUrl}/orders/${orderId}/cancel?worker_id=1`)
      showSuccessToast('工单已取消')
      fetchPendingOrders()
      fetchMyOrders()
    } catch (e) {
      showFailToast('取消失败')
    }
  }).catch(() => {
    // on cancel
  })
}

const addMaterial = (orderId: string) => {
  if (!orderMaterialsMap.value[orderId]) {
    orderMaterialsMap.value[orderId] = []
  }
  orderMaterialsMap.value[orderId].push({ search_name: '', material_id: '', quantity: 1, unit: '' })
}

const removeMaterial = (orderId: string, index: number) => {
  orderMaterialsMap.value[orderId].splice(index, 1)
}

const onMaterialSelect = (orderId: string, index: number) => {
  const mat = orderMaterialsMap.value[orderId][index]
  const found = materials.value.find(m => m.name === mat.search_name)
  if (found) {
    mat.material_id = found.id
    mat.unit = found.unit
    
    // Check if the image url is a valid string, and not 'nan' string from python pandas
    let validImg = ''
    if (found.image_url && typeof found.image_url === 'string' && found.image_url.toLowerCase() !== 'nan') {
      validImg = found.image_url
      // 如果上传的是相对路径（如 uploads/xxx），拼接上 apiBaseUrl
      if (!validImg.startsWith('http')) {
         validImg = validImg.startsWith('/') ? `${apiBaseUrl}${validImg}` : `${apiBaseUrl}/${validImg}`
      }
    }
    
    mat.image_url = validImg
  } else {
    mat.material_id = ''
    mat.image_url = ''
  }
}

const fileList = ref<any>({})
const showCompleterPopup = ref(false)
const currentOrderIdForCompleter = ref('')
const detailPopupVisible = ref(false)
const currentDetailOrder = ref<any>(null)

const openCompleterPopup = (orderId: string) => {
  currentOrderIdForCompleter.value = orderId
  if (!completers.value[orderId]) {
    completers.value[orderId] = []
  }
  showCompleterPopup.value = true
}

const getCompleterNames = (orderId: string) => {
  const ids = completers.value[orderId] || []
  return ids.map((id: number) => users.value.find((u: any) => u.id === id)?.name).filter(Boolean).join(', ') || '请选择人员 (可多选)'
}

const openOrderDetails = (order: any) => {
  if (order.status !== 'in_progress') {
    currentDetailOrder.value = order
    detailPopupVisible.value = true
  }
}

const completeOrder = async (orderId: string) => {
  const files = fileList.value[orderId] || []
  if (files.length === 0) {
    showToast('请先拍照上传完工证明')
    return
  }
  const selectedCompleters = completers.value[orderId] || []
  if (selectedCompleters.length === 0) {
    showToast('请选择完工人员')
    return
  }
  const completerNamesStr = selectedCompleters.map((id: number) => users.value.find((u: any) => u.id === id)?.name).filter(Boolean).join(', ')

  try {
    showToast({ type: 'loading', message: '提交中...', duration: 0 })
    
    // 上传多张图片
    const imageUrls = []
    for (const fileObj of files) {
      const formData = new FormData()
      formData.append('file', fileObj.file)
      const uploadRes = await axios.post(`${apiBaseUrl}/upload`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
      imageUrls.push(uploadRes.data.url)
    }

    const mats = orderMaterialsMap.value[orderId] || []
    const formattedMats = mats
      .filter((m: any) => m.material_id && m.quantity > 0)
      .map((m: any) => ({
        material_id: parseInt(m.material_id),
        quantity: parseFloat(m.quantity),
        unit: m.unit
      }))

    await axios.put(`${apiBaseUrl}/orders/${orderId}/complete`, {
      image_urls: imageUrls,
      completer_names: completerNamesStr,
      materials: formattedMats
    })
    showSuccessToast('完工提交成功')
    fetchMyOrders()
  } catch (e) {
    showFailToast('完工提交失败')
  }
}

onMounted(() => {
  fetchPendingOrders()
  fetchMyOrders()
  fetchMaterials()
  fetchUsers()
  initWebSocket()
})

onUnmounted(() => {
  if (ws) ws.close()
})
</script>

<template>
  <div class="mobile-app">
    <van-nav-bar title="技工端 - 任务大厅" fixed placeholder />

    <div class="content">
      <!-- 任务大厅 -->
      <div v-show="activeTab === 0">
        <van-empty v-if="pendingOrders.length === 0" description="暂无新任务" />
        <van-card
          v-for="order in pendingOrders"
          :key="order.id"
          :desc="order.description"
          :title="`工单号: ${order.id}`"
        >
          <template #tags>
            <van-tag type="primary">待指派</van-tag>
            <div style="margin-top: 5px; color: #999; font-size: 12px;">
              发布时间: {{ new Date(order.created_at).toLocaleString() }}
            </div>
          </template>
          <template #footer>
            <van-button size="small" type="primary" @click="claimOrder(order.id)">立即领取</van-button>
          </template>
        </van-card>
      </div>

      <!-- 我的工单 -->
      <div v-show="activeTab === 1">
        <van-empty v-if="myOrders.length === 0" description="暂无历史工单" />
        <van-card
          v-for="order in myOrders"
          :key="order.id"
          :desc="order.description"
          :title="`工单号: ${order.id}`"
          @click="openOrderDetails(order)"
        >
          <template #tags>
            <van-tag v-if="order.status === 'in_progress'" type="primary">进行中</van-tag>
            <van-tag v-else-if="order.status === 'review'" type="warning">待验收</van-tag>
            <van-tag v-else type="success">已完成</van-tag>
            
            <div style="margin-top: 5px; color: #999; font-size: 12px;">
              领取时间: {{ order.accepted_at ? new Date(order.accepted_at).toLocaleString() : '-' }}
            </div>
            
            <div v-if="order.status === 'in_progress'" @click.stop>
              <!-- 领料逻辑区域 -->
              <div style="margin-top: 10px; border-top: 1px dashed #eee; padding-top: 10px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                  <span style="color: #666; font-size: 13px;">耗材领用 (选填)</span>
                  <van-button size="mini" icon="plus" plain type="primary" @click="addMaterial(order.id)">添加物料</van-button>
                </div>
                <div v-for="(mat, index) in orderMaterialsMap[order.id]" :key="index" style="display: flex; gap: 5px; margin-bottom: 8px; align-items: center; flex-wrap: wrap;">
                  
                  <div style="width: 100%; display: flex; align-items: center; gap: 5px;">
                    <!-- 替换为原生 select 以支持更好展示 -->
                    <select 
                      v-model="mat.search_name" 
                      @change="onMaterialSelect(order.id, index)"
                      style="flex: 2; font-size: 13px; border: 1px solid #ddd; border-radius: 4px; padding: 4px; background: white;"
                    >
                      <option value="" disabled>选择材料</option>
                      <option v-for="m in materials" :key="m.id" :value="m.name">
                        {{m.name}} ({{m.category}}) | 余: {{m.stock}}
                      </option>
                    </select>
                    
                    <input v-model="mat.unit" placeholder="单位" style="flex: 1; font-size: 13px; border: 1px solid #ddd; border-radius: 4px; padding: 4px; width: 40px;" />
                    <input v-model="mat.quantity" type="number" step="0.1" style="flex: 1; font-size: 13px; border: 1px solid #ddd; border-radius: 4px; padding: 4px; width: 50px;" placeholder="数量" />
                    <van-button size="small" icon="cross" type="danger" plain @click="removeMaterial(order.id, index)"></van-button>
                  </div>
                  
                  <!-- 显示选中的材料图片 -->
                  <div v-if="mat.image_url" style="width: 100%; margin-top: 4px;">
                    <van-image :src="mat.image_url" width="40" height="40" fit="cover" radius="4" style="background-color: #f7f8fa;">
                      <template v-slot:error>图片加载失败</template>
                    </van-image>
                  </div>

                </div>
              </div>

              <!-- 完工人员与拍照 -->
              <div style="margin-top: 10px; border-top: 1px dashed #eee; padding-top: 10px;">
                <div style="margin-bottom: 8px; display: flex; align-items: center;">
                  <span style="color: #666; font-size: 13px; width: 70px;">完工人员:</span>
                  <div @click="openCompleterPopup(order.id)" style="flex: 1; font-size: 13px; border: 1px solid #ddd; border-radius: 4px; padding: 6px; background: white; min-height: 18px; color: #333;">
                    {{ getCompleterNames(order.id) }}
                  </div>
                </div>
                <div style="margin-bottom: 5px; color: #666; font-size: 13px;">上传完工证明 (最多3张)</div>
                <van-uploader v-model="fileList[order.id]" multiple :max-count="3" capture="camera" accept="image/*" />
              </div>
            </div>
            
            <div v-else style="margin-top: 10px; border-top: 1px dashed #eee; padding-top: 10px;">
              <div style="font-size: 12px; color: #666;">完工时间: {{ order.completed_at ? new Date(order.completed_at).toLocaleString() : '-' }}</div>
              <div style="font-size: 12px; color: #666;">完工人员: {{ order.completer_names || '-' }}</div>
              <div style="font-size: 12px; color: #1989fa; margin-top: 4px;">点击查看详情</div>
            </div>
          </template>
          
          <template #footer v-if="order.status === 'in_progress'">
            <van-button size="small" @click.stop="cancelOrder(order.id)">取消工单</van-button>
            <van-button size="small" type="success" @click.stop="completeOrder(order.id)">提交完工</van-button>
          </template>
        </van-card>
      </div>
      <!-- 完工人员多选弹窗 -->
      <van-popup v-model:show="showCompleterPopup" position="bottom" :style="{ height: '50%' }">
        <div style="padding: 15px; font-weight: bold; text-align: center; border-bottom: 1px solid #eee;">选择完工人员</div>
        <van-checkbox-group v-model="completers[currentOrderIdForCompleter]" style="padding: 10px 20px;">
          <van-checkbox 
            v-for="u in users" 
            :key="u.id" 
            :name="u.id" 
            style="margin-bottom: 15px;"
          >
            {{ u.name }}
          </van-checkbox>
        </van-checkbox-group>
        <div style="padding: 15px;">
          <van-button type="primary" block @click="showCompleterPopup = false">确认</van-button>
        </div>
      </van-popup>

      <!-- 历史详情弹窗 -->
      <van-popup v-model:show="detailPopupVisible" position="right" :style="{ width: '100%', height: '100%' }">
        <van-nav-bar title="工单详情" left-arrow @click-left="detailPopupVisible = false" />
        <div v-if="currentDetailOrder" style="padding: 15px;">
          <h3 style="margin-top: 0;">{{ currentDetailOrder.id }}</h3>
          <p style="color: #666; font-size: 14px;">{{ currentDetailOrder.description }}</p>
          <van-divider />
          <div style="font-size: 13px; line-height: 2;">
            <div>状态: <van-tag type="success">{{ currentDetailOrder.status === 'review' ? '待验收' : '已完成' }}</van-tag></div>
            <div>领取时间: {{ currentDetailOrder.accepted_at ? new Date(currentDetailOrder.accepted_at).toLocaleString() : '-' }}</div>
            <div>完工时间: {{ currentDetailOrder.completed_at ? new Date(currentDetailOrder.completed_at).toLocaleString() : '-' }}</div>
            <div>完工人员: {{ currentDetailOrder.completer_names || '-' }}</div>
          </div>
          
          <div v-if="currentDetailOrder.materials && currentDetailOrder.materials.length > 0">
            <van-divider>消耗物料</van-divider>
            <div v-for="(m, i) in currentDetailOrder.materials" :key="i" style="font-size: 13px; margin-bottom: 5px;">
               - 材料ID: {{ m.material_id }}, 数量: {{ m.quantity }} {{ m.unit }}
            </div>
          </div>

          <div v-if="currentDetailOrder.evidence && currentDetailOrder.evidence.length > 0">
            <van-divider>完工照片</van-divider>
            <div style="display: flex; gap: 10px; flex-wrap: wrap;">
              <van-image 
                v-for="(img, idx) in currentDetailOrder.evidence" 
                :key="idx" 
                :src="img.image_url" 
                width="80" 
                height="80" 
                fit="cover" 
                @click="showImagePreview({ images: currentDetailOrder.evidence.map((e: any) => e.image_url), startPosition: idx })"
              />
            </div>
          </div>
        </div>
      </van-popup>
    </div>

    <van-tabbar v-model="activeTab" fixed placeholder>
      <van-tabbar-item icon="home-o">任务大厅</van-tabbar-item>
      <van-tabbar-item icon="orders-o">我的工单</van-tabbar-item>
    </van-tabbar>
  </div>
</template>

<style scoped>
.mobile-app {
  background-color: #f7f8fa;
  min-height: 100vh;
}
.content {
  padding: 10px 0;
  padding-bottom: 60px;
}
</style>
