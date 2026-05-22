import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import AgentConversationPanel from '../../../src/components/agent/AgentConversationPanel.vue'

const i18n = createI18n({
  legacy: false,
  locale: 'en',
  messages: {
    en: {
      app: {
        agentConversation: 'Agent Conversation',
        user: 'User',
        agent: 'Agent',
        agentReplyPending: 'Pending',
        noConversation: 'No Conversation',
        queryPlaceholder: 'Ask anything',
        send: 'Send',
        contextFiles: 'Context files',
        evidenceSources: 'Sources',
        executionTime: 'Execution time'
      },
      project: {
        selectProjectPrompt: 'Select project'
      },
      common: {
        retry: 'Retry',
        remove: 'Remove',
        failed: 'Failed'
      }
    }
  }
})

const baseProps = {
  projectName: 'Demo',
  hasProject: true,
  loading: false,
  error: null,
  messages: [
    {
      id: 'm1',
      role: 'user',
      content: 'Hello',
      time: '10:00',
      origin: 'history',
      status: 'completed'
    }
  ],
  sending: false,
  sendError: null,
  composerDisabled: false,
  messageDraft: '',
  contextFiles: []
}

describe('AgentConversationPanel', () => {
  it('emits update and submit events from composer interactions', async () => {
    const wrapper = mount(AgentConversationPanel, {
      props: baseProps,
      global: {
        plugins: [i18n],
        stubs: {
          MarkdownRenderer: {
            template: '<div><slot /></div>'
          }
        }
      }
    })

    const textarea = wrapper.get('textarea')
    await textarea.setValue('New prompt')
    await wrapper.setProps({ messageDraft: 'New prompt' })

    expect(wrapper.emitted('update:draft')?.[0]).toEqual(['New prompt'])

    await wrapper.get('form').trigger('submit.prevent')
    expect(wrapper.emitted('submit')).toBeTruthy()
  })

  it('shows empty state when no project is selected', () => {
    const wrapper = mount(AgentConversationPanel, {
      props: {
        ...baseProps,
        hasProject: false,
        messages: []
      },
      global: {
        plugins: [i18n],
        stubs: {
          MarkdownRenderer: {
            template: '<div><slot /></div>'
          }
        }
      }
    })

    expect(wrapper.text()).toContain('Select project')
  })
})

