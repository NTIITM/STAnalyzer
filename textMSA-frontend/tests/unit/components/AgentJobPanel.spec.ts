import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import AgentJobPanel from '../../../src/components/agent/AgentJobPanel.vue'

const jobFixture = {
  job_id: 'job-1',
  status: 'running',
  started_at: '2025-01-01T00:00:00Z',
  updated_at: '2025-01-01T00:05:00Z',
  progress: {
    current_step: 'tool_selector',
    step_detail: 'Scoring relevant tools'
  }
}

const i18n = createI18n({
  legacy: false,
  locale: 'en',
  messages: {
    en: {
      app: {
        agentJobPanelTitle: 'Job status',
        agentPollingActive: 'Polling',
        agentPollingIdle: 'Idle',
        agentPollingStopped: 'Stopped',
        agentComposerLocked: 'Composer locked',
        agentNoActiveJob: 'No active job',
        agentRecentJobs: 'Recent jobs',
        agentNoHistory: 'No history',
        agentJobRunning: 'Running',
        agentJobQueued: 'Queued',
        agentJobPanelBody: 'Body',
        stopJob: 'Stop',
        startedAt: 'Started at',
        updatedAt: 'Updated at'
      },
      common: {
        refresh: 'Refresh',
        completed: 'Completed',
        cancelled: 'Cancelled',
        failed: 'Failed'
      }
    }
  }
})

describe('AgentJobPanel', () => {
  it('emits stop event when stop button clicked', async () => {
    const wrapper = mount(AgentJobPanel, {
      props: {
        activeJob: jobFixture,
        composerLocked: false,
        pollingStatus: 'running',
        lastPolledAt: '2025-01-01T00:05:00Z',
        jobsLoading: false,
        jobsError: null,
        stopJobState: 'idle',
        stopJobError: null
      },
      global: {
        plugins: [i18n]
      }
    })

    await wrapper.get('.stop-button').trigger('click')

    expect(wrapper.emitted('stop')?.[0]).toEqual(['job-1'])
  })

  it('renders composer lock banner when locked', () => {
    const wrapper = mount(AgentJobPanel, {
      props: {
        activeJob: null,
        composerLocked: true,
        pollingStatus: 'idle',
        lastPolledAt: null,
        jobsLoading: false,
        jobsError: null,
        stopJobState: 'idle',
        stopJobError: null
      },
      global: {
        plugins: [i18n]
      }
    })

    expect(wrapper.text()).toContain('Composer locked')
  })
})

