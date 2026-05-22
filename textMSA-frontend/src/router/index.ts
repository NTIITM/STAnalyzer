/**
 * Vue Router 路由配置
 * 所有页面组件使用懒加载（动态 import），实现按需加载和代码分割
 */
import { createRouter, createWebHistory, type RouteLocationNormalized, type NavigationGuardNext } from 'vue-router'
import { tokenManager } from '../api/request'

// 懒加载路由组件
const AnalysisPanel = () => import('../components/AnalysisPanel.vue')
const ServiceManagement = () => import('../components/service/ServiceManagement.vue')
const ServiceFormPage = () => import('../components/service/ServiceFormPage.vue')
const ProjectConfigPage = () => import('../components/project/ProjectConfigPage.vue')
const HelpPage = () => import('../components/HelpPageNew.vue')
const UserProfilePage = () => import('../components/user/UserProfilePage.vue')
const CodegenPage = () => import('../views/CodegenPage.vue')
const DataAnalysisPage = () => import('../views/DataAnalysisPage.vue')
const ServiceFileTypeGraph = () => import('../components/service/ServiceFileTypeGraph.vue')
const ExecutionManagement = () => import('../components/execution/ExecutionManagement.vue')
const ServiceExecutePage = () => import('../views/ServiceExecutePage.vue')

const routes = [
  {
    path: '/',
    redirect: '/analysis'
  },
  {
    path: '/codegen',
    name: 'Codegen',
    component: CodegenPage
  },
  {
    path: '/analysis',
    name: 'Analysis',
    component: AnalysisPanel
  },
  {
    path: '/data-analysis',
    name: 'DataAnalysis',
    component: DataAnalysisPage
  },
  {
    path: '/services',
    name: 'Services',
    component: ServiceManagement
  },
  // {
  //   path: '/knowledge',
  //   name: 'Knowledge',
  //   component: KnowledgeWorkspace
  // },
  // {
  //   path: '/knowledge/create',
  //   name: 'KnowledgeCreate',
  //   component: KnowledgeFormPage
  // },
  // {
  //   path: '/knowledge/edit/:id',
  //   name: 'KnowledgeEdit',
  //   component: KnowledgeFormPage,
  //   props: true
  // },
  // {
  //   path: '/knowledge/prompts',
  //   name: 'KnowledgePrompts',
  //   component: KnowledgePromptCenter
  // },
  // {
  //   path: '/knowledge-search',
  //   name: 'KnowledgeSearch',
  //   component: KnowledgeSearchPage,
  //   props: (route: RouteLocationNormalized) => ({
  //     projectId: route.query.projectId as string | undefined
  //   })
  // },
  // {
  //   path: '/knowledge-search/create',
  //   name: 'KnowledgeSearchCreate',
  //   component: KnowledgeSearchCreatePage,
  //   props: (route: RouteLocationNormalized) => ({
  //     projectId: route.query.projectId as string | undefined
  //   })
  // },
  {
    path: '/services/create',
    name: 'ServiceCreate',
    component: ServiceFormPage
  },
  {
    path: '/services/edit/:id',
    name: 'ServiceEdit',
    component: ServiceFormPage,
    props: true
  },
  {
    path: '/services/graph',
    name: 'ServiceFileTypeGraph',
    component: ServiceFileTypeGraph,
    props: (route: RouteLocationNormalized) => ({
      projectId: route.query.projectId,
      fileTypeId: route.query.fileTypeId,
      depth: route.query.depth ? parseInt(route.query.depth as string) : undefined
    })
  },
  {
    path: '/projects/create',
    name: 'ProjectCreate',
    component: ProjectConfigPage,
    props: true
  },
  {
    path: '/executions',
    name: 'Executions',
    component: ExecutionManagement,
    props: (route: RouteLocationNormalized) => ({
      project: route.query.project,
      serviceId: route.query.service_id,
      status: route.query.status
    })
  },
  {
    path: '/projects/:id/config',
    name: 'ProjectConfig',
    component: ProjectConfigPage,
    props: true
  },
  {
    path: '/service/execute/:serviceId?',
    name: 'ServiceExecutePage',
    component: ServiceExecutePage,
    props: (route: RouteLocationNormalized) => ({
      serviceId: route.params.serviceId as string | undefined,
      projectId: route.query.projectId as string | undefined,
      initialFileId: route.query.fileId || route.query.initialFileId,
      origin: route.query.origin as string | undefined
    })
  },
  {
    path: '/help',
    name: 'Help',
    component: HelpPage
  },
  {
    path: '/profile',
    name: 'Profile',
    component: UserProfilePage
  },
  // {
  //   path: '/spatial-coexpression',
  //   name: 'SpatialCoexpression',
  //   component: SpatialCoexpressionNetworkPage
  // },
  // {
  //   path: '/spatial-transcriptomics',
  //   name: 'SpatialTranscriptomics',
  //   component: SpatialTranscriptomicsPage
  // },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    redirect: '/help'
  }
]

const router = createRouter({
  history: createWebHistory('/STAnalyzer/'),
  routes
})

/**
 * 路由守卫：检查 Token 认证
 * 如果访问非 HelpPage 且没有 Token，重定向到帮助文档
 */
router.beforeEach((to, _from, next: NavigationGuardNext) => {
  // HelpPage 不需要认证，直接通过
  if (to.path === '/help') {
    next()
    return
  }
  
  // 检查是否有 Token
  if (!tokenManager.isAuthenticated()) {
    // 没有 Token，重定向到帮助文档
    next('/help')
    return
  }
  
  // 有 Token，允许访问
  next()
})

export default router
