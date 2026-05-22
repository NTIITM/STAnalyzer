<template>
  <component :is="iconComponent" :class="['icon', sizeClass]" />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import {
  AdjustmentsHorizontalIcon,
  ArrowDownTrayIcon,
  ChevronDoubleDownIcon,
  ChevronDoubleRightIcon,
  ChevronDoubleLeftIcon,
  ChatBubbleLeftEllipsisIcon,
  ArrowLeftIcon,
  ArrowRightIcon,
  ArrowPathIcon,
  ArrowUpTrayIcon,
  BeakerIcon,
  BookmarkIcon,
  BookOpenIcon,
  ChartBarIcon,
  ChevronDownIcon,
  CodeBracketIcon,
  CogIcon,
  DocumentIcon,
  EllipsisVerticalIcon,
  ExclamationTriangleIcon,
  EyeIcon,
  FolderIcon,
  GlobeAltIcon,
  InformationCircleIcon,
  LockClosedIcon,
  MagnifyingGlassIcon,
  PencilIcon,
  PlayIcon,
  PlusIcon,
  QuestionMarkCircleIcon,
  QueueListIcon,
  RectangleStackIcon,
  RocketLaunchIcon,
  ShareIcon,
  ShieldCheckIcon,
  SparklesIcon,
  TrashIcon,
  UserGroupIcon,
  UserIcon,
  XMarkIcon,
  LightBulbIcon,
  PresentationChartLineIcon,
  ChartPieIcon,
  DocumentTextIcon,
  Cog6ToothIcon,
  CircleStackIcon,
  ChatBubbleLeftRightIcon,
  StarIcon,
  CheckBadgeIcon,
  ListBulletIcon,
  CursorArrowRaysIcon
} from '@heroicons/vue/24/outline'

const props = defineProps<{
  name: string
  size?: 'sm' | 'md' | 'lg'
}>()

const sizeClass = computed(() => {
  return `icon-${props.size || 'md'}`
})

const iconMap: Record<string, any> = {
  'knowledge': BookOpenIcon,
  'analysis': ChartBarIcon,
  'database': CircleStackIcon,
  'message': ChatBubbleLeftRightIcon,
  'file-text': DocumentIcon,
  'refresh-cw': ArrowPathIcon,
  'check': CheckBadgeIcon,
  'activity': PlayIcon,
  'results': PresentationChartLineIcon,
  'report': DocumentTextIcon,
  'chart': ChartBarIcon,
  'chart-pie': ChartPieIcon,
  'services': Cog6ToothIcon,
  'star-square': StarIcon,
  'star': SparklesIcon,
  'tasks': CogIcon,
  'settings': CogIcon,
  'user': UserIcon,
  'edit': PencilIcon,
  'pencil': PencilIcon,
  'delete': TrashIcon,
  'trash': TrashIcon,
  'play': PlayIcon,
  'execute': PlayIcon,
  'document': DocumentIcon,
  'file': DocumentIcon,
  'json': DocumentIcon,
  'plus': PlusIcon,
  'add': PlusIcon,
  'close': XMarkIcon,
  'x': XMarkIcon,
  'chevron-down': ChevronDownIcon,
  'dropdown': ChevronDownIcon,
  'more': EllipsisVerticalIcon,
  'dots': EllipsisVerticalIcon,
  'dna': BeakerIcon,
  'logo': BeakerIcon,
  'beaker': BeakerIcon,
  'help': QuestionMarkCircleIcon,
  'question': QuestionMarkCircleIcon,
  'rocket': RocketLaunchIcon,
  'code': CodeBracketIcon,
  'info': InformationCircleIcon,
  'information': InformationCircleIcon,
  'share': ShareIcon,
  'lock': LockClosedIcon,
  'layout': ListBulletIcon,
  'globe': GlobeAltIcon,
  'shield': ShieldCheckIcon,
  'right': ArrowRightIcon,
  'refresh': ArrowPathIcon,
  'loading': ArrowPathIcon,
  'search': MagnifyingGlassIcon,
  'warning': ExclamationTriangleIcon,
  'sparkles': SparklesIcon,
  'upload': ArrowUpTrayIcon,
  'download': ArrowDownTrayIcon,
  'timeline': QueueListIcon,
  'save': BookmarkIcon,
  'sort': AdjustmentsHorizontalIcon,
  'folder': FolderIcon,
  'visualization': EyeIcon,
  'documentation': BookOpenIcon,
  'community': UserGroupIcon,
  'arrow-left': ChevronDoubleLeftIcon,
  'back': ArrowLeftIcon,
  'diagram': RectangleStackIcon,
  'graph': RectangleStackIcon,
  'arrow-down': ChevronDoubleDownIcon,
  'arrow-right': ChevronDoubleRightIcon,
  'light-bulb': LightBulbIcon,
  'context': BookOpenIcon,
  'overview': EyeIcon,
  'robot': ChatBubbleLeftEllipsisIcon,
  'cursor': CursorArrowRaysIcon
}

const iconComponent = computed(() => {
  return iconMap[props.name] || DocumentIcon
})
</script>

<style scoped>
.icon {
  display: inline-block;
  flex-shrink: 0;
}

.icon-sm {
  width: 16px;
  height: 16px;
}

.icon-md {
  width: 20px;
  height: 20px;
}

.icon-lg {
  width: 24px;
  height: 24px;
}
</style>
