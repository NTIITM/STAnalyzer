<template>
  <div class="help-page">
    <div class="help-container">
      <!-- 侧边栏导航 -->
      <div class="help-sidebar">
        <div class="sidebar-header">
          <Icon name="help" size="lg" class="header-icon" />
          <h2>{{ $t('help.title') }}</h2>
        </div>
        <nav class="sidebar-nav">
          <a 
            v-for="section in sections" 
            :key="section.id"
            :href="`#${section.id}`"
            class="nav-link"
            :class="{ active: activeSection === section.id }"
            @click.prevent="scrollToSection(section.id)"
          >
            <Icon :name="section.icon" size="sm" class="nav-icon" />
            <span>{{ section.title }}</span>
          </a>
        </nav>
      </div>

      <!-- 主内容区域 -->
      <div class="help-content" ref="contentRef">
        <!-- 介绍部分 -->
        <section id="introduction" class="help-section">
          <div class="section-header">
            <Icon name="info" size="lg" class="section-icon" />
            <h1>{{ $t('help.introduction.title') }}</h1>
          </div>

          <div class="feature-card">
            <h2>{{ $t('help.introduction.whatIs.title') }}</h2>
            <div v-html="formatMarkdown($t('help.introduction.whatIs.description'))"></div>
          </div>

          <div class="feature-card">
            <h2>{{ $t('help.introduction.coreFeatures.title') }}</h2>
            <ul class="feature-list">
              <li v-for="(item, index) in getItems('help.introduction.coreFeatures.items')" :key="index" v-html="formatMarkdown(item)"></li>
            </ul>
          </div>

          <div class="feature-card">
            <h2>{{ $t('help.introduction.advantages.title') }}</h2>
            <ul class="feature-list">
              <li v-for="(item, index) in getItems('help.introduction.advantages.items')" :key="index" v-html="formatMarkdown(item)"></li>
            </ul>
          </div>

          <div class="image-container">
            <img :src="getImagePath('framework.png')" :alt="$t('help.introduction.frameworkImage')" />
            <p class="image-caption">{{ $t('help.introduction.frameworkImage') }}</p>
          </div>
        </section>

        <!-- Getting Started -->
        <section id="getting-started" class="help-section">
          <div class="section-header">
            <Icon name="rocket" size="lg" class="section-icon" />
            <h1>{{ $t('help.sections.gettingStarted.title') }}</h1>
          </div>
          <p class="section-description">
            {{ $t('help.sections.gettingStarted.description') }}
          </p>

          <!-- 1. 创建项目 -->
          <div class="feature-card">
            <h2>{{ $t('help.sections.gettingStarted.steps.createProject.title') }}</h2>
            <p>{{ $t('help.sections.gettingStarted.steps.createProject.description') }}</p>
            <h3>{{ $t('help.sections.gettingStarted.steps.createProject.steps.0') }}</h3>
            <ol class="step-list">
              <li v-for="(step, index) in getSteps('help.sections.gettingStarted.steps.createProject.steps')" :key="index" v-html="formatMarkdown(step)"></li>
            </ol>
            <div class="info-box info-tip">
              <strong>{{ $t('help.sections.gettingStarted.steps.createProject.purpose.title') }}</strong>
              <ul>
                <li v-for="(item, index) in getItems('help.sections.gettingStarted.steps.createProject.purpose.items')" :key="index">{{ item }}</li>
              </ul>
            </div>
            <div class="image-container">
              <img :src="getImagePath('create_project.png')" :alt="$t('help.sections.gettingStarted.steps.createProject.image')" />
              <p class="image-caption">{{ $t('help.sections.gettingStarted.steps.createProject.image') }}</p>
            </div>
            <div class="info-box info-tip">
              <p v-html="formatMarkdown($t('help.sections.gettingStarted.steps.createProject.tip'))"></p>
            </div>
          </div>

          <!-- 2. 上传数据 -->
          <div class="feature-card">
            <h2>{{ $t('help.sections.gettingStarted.steps.uploadData.title') }}</h2>
            <p>{{ $t('help.sections.gettingStarted.steps.uploadData.description') }}</p>
            <h3>{{ $t('help.sections.gettingStarted.steps.uploadData.steps.0') }}</h3>
            <ol class="step-list">
              <li v-for="(step, index) in getSteps('help.sections.gettingStarted.steps.uploadData.steps')" :key="index" v-html="formatMarkdown(step)"></li>
            </ol>
            <div class="info-box info-tip">
              <strong>{{ $t('help.sections.gettingStarted.steps.uploadData.autoProcessing.title') }}</strong>
              <ul>
                <li v-for="(item, index) in getItems('help.sections.gettingStarted.steps.uploadData.autoProcessing.items')" :key="index">{{ item }}</li>
              </ul>
            </div>
            <div class="image-container">
              <img :src="getImagePath('upload_data.png')" :alt="$t('help.sections.gettingStarted.steps.uploadData.image')" />
              <p class="image-caption">{{ $t('help.sections.gettingStarted.steps.uploadData.image') }}</p>
            </div>
            <div class="info-box info-warning">
              <strong>{{ $t('help.sections.gettingStarted.steps.uploadData.notes.title') }}</strong>
              <ul>
                <li v-for="(item, index) in getItems('help.sections.gettingStarted.steps.uploadData.notes.items')" :key="index">{{ item }}</li>
              </ul>
            </div>
          </div>

          <!-- 3. 加入上下文 -->
          <div class="feature-card">
            <h2>{{ $t('help.sections.gettingStarted.steps.addContext.title') }}</h2>
            <p>{{ $t('help.sections.gettingStarted.steps.addContext.description') }}</p>
            <div class="info-box info-tip">
              <strong>{{ $t('help.sections.gettingStarted.steps.addContext.whatIsContext.title') }}</strong>
              <p>{{ $t('help.sections.gettingStarted.steps.addContext.whatIsContext.description') }}</p>
            </div>
            <h3>{{ $t('help.sections.gettingStarted.steps.addContext.steps.0') }}</h3>
            <ol class="step-list">
              <li v-for="(step, index) in getSteps('help.sections.gettingStarted.steps.addContext.steps')" :key="index" v-html="formatMarkdown(step)"></li>
            </ol>
            <div class="info-box info-tip">
              <strong>{{ $t('help.sections.gettingStarted.steps.addContext.suggestions.title') }}</strong>
              <ul>
                <li v-for="(item, index) in getItems('help.sections.gettingStarted.steps.addContext.suggestions.items')" :key="index" v-html="formatMarkdown(item)"></li>
              </ul>
            </div>
            <div class="image-container">
              <img :src="getImagePath('add_file_to_context.png')" :alt="$t('help.sections.gettingStarted.steps.addContext.image')" />
              <p class="image-caption">{{ $t('help.sections.gettingStarted.steps.addContext.image') }}</p>
            </div>
            <div class="info-box info-tip">
              <p v-html="formatMarkdown($t('help.sections.gettingStarted.steps.addContext.tip'))"></p>
            </div>
          </div>

          <!-- 4. 输入查询 -->
          <div class="feature-card">
            <h2>{{ $t('help.sections.gettingStarted.steps.askAgent.title') }}</h2>
            <p>{{ $t('help.sections.gettingStarted.steps.askAgent.description') }}</p>
            <h3>{{ $t('help.sections.gettingStarted.steps.askAgent.howToUse.title') }}</h3>
              <ol class="step-list">
                <li v-for="(step, index) in getSteps('help.sections.gettingStarted.steps.askAgent.howToUse.steps')" :key="index" v-html="formatMarkdown(step)"></li>
              </ol>
            <div class="image-container">
              <img :src="getImagePath('send_query.png')" :alt="$t('help.sections.gettingStarted.steps.askAgent.images.sendQuery')" />
              <p class="image-caption">{{ $t('help.sections.gettingStarted.steps.askAgent.imageCaptions.sendQuery') }}</p>
            </div>
            <h3>{{ $t('help.sections.gettingStarted.steps.askAgent.workflow.title') }}</h3>
              <p>{{ $t('help.sections.gettingStarted.steps.askAgent.workflow.description') }}</p>
              <ol class="step-list">
                <li v-for="(step, index) in getSteps('help.sections.gettingStarted.steps.askAgent.workflow.steps')" :key="index" v-html="formatMarkdown(step)"></li>
              </ol>
            <div class="image-container">
              <img :src="getImagePath('agent_generate_plans.png')" :alt="$t('help.sections.gettingStarted.steps.askAgent.images.generatePlans')" />
              <p class="image-caption">{{ $t('help.sections.gettingStarted.steps.askAgent.imageCaptions.generatePlans') }}</p>
            </div>
            <div class="image-container">
              <img :src="getImagePath('agent_invoke_service.png')" :alt="$t('help.sections.gettingStarted.steps.askAgent.images.invokeService')" />
              <p class="image-caption">{{ $t('help.sections.gettingStarted.steps.askAgent.imageCaptions.invokeService') }}</p>
            </div>
            <div class="image-container">
              <img :src="getImagePath('agent_generate_files.png')" :alt="$t('help.sections.gettingStarted.steps.askAgent.images.generateFiles')" />
              <p class="image-caption">{{ $t('help.sections.gettingStarted.steps.askAgent.imageCaptions.generateFiles') }}</p>
            </div>
            <div class="image-container">
              <img :src="getImagePath('agent_read_files.png')" :alt="$t('help.sections.gettingStarted.steps.askAgent.images.readFiles')" />
              <p class="image-caption">{{ $t('help.sections.gettingStarted.steps.askAgent.images.readFiles') }}</p>
            </div>
            <div class="image-container">
              <img :src="getImagePath('agent_retrieve_literature.png')" :alt="$t('help.sections.gettingStarted.steps.askAgent.images.retrieveLiterature')" />
              <p class="image-caption">{{ $t('help.sections.gettingStarted.steps.askAgent.imageCaptions.retrieveLiterature') }}</p>
            </div>
          </div>

          <!-- 5. 获得报告 -->
          <div class="feature-card">
            <h2>{{ $t('help.sections.gettingStarted.steps.viewReport.title') }}</h2>
            <p>{{ $t('help.sections.gettingStarted.steps.viewReport.description') }}</p>
            <ul class="feature-list">
              <li v-for="(item, index) in getItems('help.sections.gettingStarted.steps.viewReport.reportContent')" :key="index" v-html="formatMarkdown(item)"></li>
            </ul>
            <p>{{ $t('help.sections.gettingStarted.steps.viewReport.note') }}</p>
            <div class="image-container">
              <img :src="getImagePath('agent_generate_conclusion.png')" :alt="$t('help.sections.gettingStarted.steps.viewReport.image')" />
              <p class="image-caption">{{ $t('help.sections.gettingStarted.steps.viewReport.image') }}</p>
            </div>
          </div>
        </section>

        <!-- 分析页面 -->
        <section id="analysis-page" class="help-section">
          <div class="section-header">
            <Icon name="analysis" size="lg" class="section-icon" />
            <h1>{{ $t('help.sections.analysisPage.title') }}</h1>
          </div>
          <p class="section-description" v-html="formatMarkdown($t('help.sections.analysisPage.description'))"></p>
          
          <div class="image-container">
            <img :src="getImagePath('analysis_page.png')" :alt="$t('help.sections.analysisPage.overviewImage')" />
            <p class="image-caption">{{ $t('help.sections.analysisPage.overviewImage') }}</p>
          </div>

          <div class="feature-card">
            <h2>{{ $t('help.sections.analysisPage.pageStructure.title') }}</h2>
            <p>{{ $t('help.sections.analysisPage.pageStructure.description') }}</p>
            <ul class="feature-list">
              <li v-for="(part, index) in getItems('help.sections.analysisPage.pageStructure.parts')" :key="index" v-html="formatMarkdown(part)"></li>
            </ul>
          </div>

          <div class="feature-card">
            <h2>{{ $t('help.sections.analysisPage.leftPanel.title') }}</h2>
            <p>{{ $t('help.sections.analysisPage.leftPanel.description') }}</p>
            <h3>{{ $t('help.sections.analysisPage.leftPanel.projectList.title') }}</h3>
            <ul class="feature-list">
              <li v-for="(item, index) in getItems('help.sections.analysisPage.leftPanel.projectList.items')" :key="index" v-html="formatMarkdown(item)"></li>
            </ul>
            <h3>{{ $t('help.sections.analysisPage.leftPanel.fileList.title') }}</h3>
            <ul class="feature-list">
              <li v-for="(item, index) in getItems('help.sections.analysisPage.leftPanel.fileList.items')" :key="index" v-html="formatMarkdown(item)"></li>
            </ul>
            <h3>{{ $t('help.sections.analysisPage.leftPanel.features.title') }}</h3>
            <ul class="feature-list">
              <li v-for="(item, index) in getItems('help.sections.analysisPage.leftPanel.features.items')" :key="index">{{ item }}</li>
            </ul>
          </div>

          <div class="feature-card">
            <h2>{{ $t('help.sections.analysisPage.middleContent.title') }}</h2>
            <p>{{ $t('help.sections.analysisPage.middleContent.description') }}</p>
            <h3>{{ $t('help.sections.analysisPage.middleContent.dagView.title') }}</h3>
            <p>{{ $t('help.sections.analysisPage.middleContent.dagView.description') }}</p>
            <div class="info-box info-tip">
              <strong>{{ $t('help.sections.analysisPage.middleContent.dagView.elements.title') }}</strong>
              <p v-html="formatMarkdown($t('help.sections.analysisPage.middleContent.dagView.elements.nodes'))"></p>
              <ul>
                <li v-for="(detail, index) in getItems('help.sections.analysisPage.middleContent.dagView.elements.nodesDetails')" :key="index">{{ detail }}</li>
              </ul>
              <p v-html="formatMarkdown($t('help.sections.analysisPage.middleContent.dagView.elements.edges'))"></p>
              <ul>
                <li v-for="(detail, index) in getItems('help.sections.analysisPage.middleContent.dagView.elements.edgesDetails')" :key="index">{{ detail }}</li>
              </ul>
              <p v-html="formatMarkdown($t('help.sections.analysisPage.middleContent.dagView.elements.files'))"></p>
            </div>
            <div class="info-box info-tip">
              <strong>{{ $t('help.sections.analysisPage.middleContent.dagView.useCases.title') }}</strong>
              <ul>
                <li v-for="(item, index) in getItems('help.sections.analysisPage.middleContent.dagView.useCases.items')" :key="index">{{ item }}</li>
              </ul>
            </div>
            <h3>{{ $t('help.sections.analysisPage.middleContent.dataVisualization.title') }}</h3>
            <ul class="feature-list">
              <li v-for="(item, index) in getItems('help.sections.analysisPage.middleContent.dataVisualization.items')" :key="index" v-html="formatMarkdown(item)"></li>
            </ul>
            <div class="image-container">
              <img :src="getImagePath('file_preview.png')" :alt="$t('help.sections.analysisPage.middleContent.dataVisualization.image')" />
              <p class="image-caption">{{ $t('help.sections.analysisPage.middleContent.dataVisualization.image') }}</p>
            </div>
          </div>

          <div class="feature-card">
            <h2>{{ $t('help.sections.analysisPage.rightPanel.title') }}</h2>
            <p>{{ $t('help.sections.analysisPage.rightPanel.description') }}</p>
            <p v-html="formatMarkdown($t('help.sections.analysisPage.rightPanel.displayCondition'))"></p>
            <div class="info-box info-tip">
              <strong>{{ $t('help.sections.analysisPage.rightPanel.mainFunctions.title') }}</strong>
              <ul>
                <li v-for="(item, index) in getItems('help.sections.analysisPage.rightPanel.mainFunctions.items')" :key="index" v-html="formatMarkdown(item)"></li>
              </ul>
            </div>
            <div class="info-box info-tip">
              <strong>{{ $t('help.sections.analysisPage.rightPanel.uiFeatures.title') }}</strong>
              <ul>
                <li v-for="(item, index) in getItems('help.sections.analysisPage.rightPanel.uiFeatures.items')" :key="index">{{ item }}</li>
              </ul>
            </div>
          </div>

          <div class="feature-card">
            <h2>{{ $t('help.sections.analysisPage.manualExecution.title') }}</h2>
            <p>{{ $t('help.sections.analysisPage.manualExecution.description') }}</p>
            <h3>{{ $t('help.sections.analysisPage.manualExecution.stepsTitle') }}</h3>
            <ol class="step-list">
              <li>
                <strong v-html="formatMarkdown($t('help.sections.analysisPage.manualExecution.step1.title'))"></strong>
                <p v-html="formatMarkdown($t('help.sections.analysisPage.manualExecution.step1.description'))"></p>
                <div class="image-container">
                  <img :src="getImagePath('manual_execution_open.png')" :alt="$t('help.sections.analysisPage.manualExecution.step1.image')" />
                  <p class="image-caption">{{ $t('help.sections.analysisPage.manualExecution.step1.image') }}</p>
                </div>
              </li>
              <li>
                <strong v-html="formatMarkdown($t('help.sections.analysisPage.manualExecution.step2.title'))"></strong>
                <p v-html="formatMarkdown($t('help.sections.analysisPage.manualExecution.step2.description'))"></p>
                <ul class="feature-list">
                  <li v-for="(item, index) in getItems('help.sections.analysisPage.manualExecution.step2.items')" :key="index" v-html="formatMarkdown(item)"></li>
                </ul>
                <div class="image-container">
                  <img :src="getImagePath('manual_execution_params.png')" :alt="$t('help.sections.analysisPage.manualExecution.step2.image')" />
                  <p class="image-caption">{{ $t('help.sections.analysisPage.manualExecution.step2.image') }}</p>
                </div>
              </li>
              <li>
                <strong v-html="formatMarkdown($t('help.sections.analysisPage.manualExecution.step3.title'))"></strong>
                <p v-html="formatMarkdown($t('help.sections.analysisPage.manualExecution.step3.description'))"></p>
                <ul class="feature-list">
                  <li v-for="(item, index) in getItems('help.sections.analysisPage.manualExecution.step3.items')" :key="index" v-html="formatMarkdown(item)"></li>
                </ul>
                <div class="image-container">
                  <img :src="getImagePath('manual_execution_running.png')" :alt="$t('help.sections.analysisPage.manualExecution.step3.image')" />
                  <p class="image-caption">{{ $t('help.sections.analysisPage.manualExecution.step3.image') }}</p>
                </div>
              </li>
              <li>
                <strong v-html="formatMarkdown($t('help.sections.analysisPage.manualExecution.step4.title'))"></strong>
                <p v-html="formatMarkdown($t('help.sections.analysisPage.manualExecution.step4.description'))"></p>
                <ul class="feature-list">
                  <li v-for="(item, index) in getItems('help.sections.analysisPage.manualExecution.step4.items')" :key="index" v-html="formatMarkdown(item)"></li>
                </ul>
              </li>
            </ol>
          </div>
        </section>

        <!-- 数据分析页面 -->
        <section id="data-analysis-page" class="help-section">
          <div class="section-header">
            <Icon name="visualization" size="lg" class="section-icon" />
            <h1>{{ $t('help.sections.dataAnalysisPage.title') }}</h1>
          </div>
          <p class="section-description" v-html="formatMarkdown($t('help.sections.dataAnalysisPage.description'))"></p>

          <div class="feature-card">
            <h2>{{ $t('help.sections.dataAnalysisPage.supportedViews.title') }}</h2>
            <ul class="feature-list">
              <li v-for="(item, index) in getItems('help.sections.dataAnalysisPage.supportedViews.items')" :key="index" v-html="formatMarkdown(item)"></li>
            </ul>
          </div>

          <div class="feature-card">
            <h2>{{ $t('help.sections.dataAnalysisPage.filePerspective.title') }}</h2>
            <p>{{ $t('help.sections.dataAnalysisPage.filePerspective.description') }}</p>
            <ul class="feature-list">
              <li v-for="(question, index) in getItems('help.sections.dataAnalysisPage.filePerspective.questions')" :key="index">{{ question }}</li>
            </ul>
            <h3>{{ $t('help.sections.dataAnalysisPage.filePerspective.supportedFileTypes.title') }}</h3>
            <p>{{ $t('help.sections.dataAnalysisPage.filePerspective.supportedFileTypes.description') }}</p>
            <ul class="feature-list">
              <li v-for="(category, index) in getItems('help.sections.dataAnalysisPage.filePerspective.supportedFileTypes.categories')" :key="index" v-html="formatMarkdown(category)"></li>
            </ul>
            <h3>{{ $t('help.sections.dataAnalysisPage.filePerspective.steps.title') }}</h3>
            <div class="info-box info-tip">
              <strong v-html="formatMarkdown($t('help.sections.dataAnalysisPage.filePerspective.steps.selectFile.title'))"></strong>
              <ul>
                <li v-for="(item, index) in getItems('help.sections.dataAnalysisPage.filePerspective.steps.selectFile.items')" :key="index" v-html="formatMarkdown(item)"></li>
              </ul>
            </div>
            <div class="info-box info-tip">
              <strong v-html="formatMarkdown($t('help.sections.dataAnalysisPage.filePerspective.steps.interactWithAgent.title'))"></strong>
              <p>{{ $t('help.sections.dataAnalysisPage.filePerspective.steps.interactWithAgent.description') }}</p>
              <p v-html="formatMarkdown($t('help.sections.dataAnalysisPage.filePerspective.steps.interactWithAgent.examples.title'))"></p>
              <ul>
                <li v-for="(example, index) in getItems('help.sections.dataAnalysisPage.filePerspective.steps.interactWithAgent.examples.items')" :key="index">{{ example }}</li>
              </ul>
              <p v-html="formatMarkdown($t('help.sections.dataAnalysisPage.filePerspective.steps.interactWithAgent.agentProvides.title'))"></p>
              <ul>
                <li v-for="(item, index) in getItems('help.sections.dataAnalysisPage.filePerspective.steps.interactWithAgent.agentProvides.items')" :key="index" v-html="formatMarkdown(item)"></li>
              </ul>
            </div>
            <div class="image-container">
              <img :src="getImagePath('data_analysis_file.png')" :alt="$t('help.sections.dataAnalysisPage.filePerspective.image')" />
              <p class="image-caption">{{ $t('help.sections.dataAnalysisPage.filePerspective.image') }}</p>
            </div>
          </div>

          <div class="feature-card">
            <h2>{{ $t('help.sections.dataAnalysisPage.executionPerspective.title') }}</h2>
            <p v-html="formatMarkdown($t('help.sections.dataAnalysisPage.executionPerspective.description'))"></p>
            <h3>{{ $t('help.sections.dataAnalysisPage.executionPerspective.suitableQuestions.title') }}</h3>
            <ul class="feature-list">
              <li v-for="(question, index) in getItems('help.sections.dataAnalysisPage.executionPerspective.suitableQuestions.items')" :key="index">{{ question }}</li>
            </ul>
            <h3>{{ $t('help.sections.dataAnalysisPage.executionPerspective.supportedContent.title') }}</h3>
            <p>{{ $t('help.sections.dataAnalysisPage.executionPerspective.supportedContent.description') }}</p>
            <div class="info-box info-tip">
              <strong v-html="formatMarkdown($t('help.sections.dataAnalysisPage.executionPerspective.supportedContent.singleExecution.title'))"></strong>
              <ul>
                <li v-for="(item, index) in getItems('help.sections.dataAnalysisPage.executionPerspective.supportedContent.singleExecution.items')" :key="index">{{ item }}</li>
              </ul>
            </div>
            <h3>{{ $t('help.sections.dataAnalysisPage.executionPerspective.steps.title') }}</h3>
            <div class="info-box info-tip">
              <strong v-html="formatMarkdown($t('help.sections.dataAnalysisPage.executionPerspective.steps.selectExecution.title'))"></strong>
              <ul>
                <li v-for="(item, index) in getItems('help.sections.dataAnalysisPage.executionPerspective.steps.selectExecution.items')" :key="index">{{ item }}</li>
              </ul>
            </div>
            <div class="info-box info-tip">
              <strong v-html="formatMarkdown($t('help.sections.dataAnalysisPage.executionPerspective.steps.viewExecutionDetails.title'))"></strong>
              <p v-html="formatMarkdown($t('help.sections.dataAnalysisPage.executionPerspective.steps.viewExecutionDetails.middleArea.title'))"></p>
              <ul>
                <li v-for="(item, index) in getItems('help.sections.dataAnalysisPage.executionPerspective.steps.viewExecutionDetails.middleArea.items')" :key="index">{{ item }}</li>
              </ul>
              <p v-html="formatMarkdown($t('help.sections.dataAnalysisPage.executionPerspective.steps.viewExecutionDetails.executionInfoPanel.title'))"></p>
              <ul>
                <li v-for="(item, index) in getItems('help.sections.dataAnalysisPage.executionPerspective.steps.viewExecutionDetails.executionInfoPanel.items')" :key="index">{{ item }}</li>
              </ul>
            </div>
            <div class="info-box info-tip">
              <strong v-html="formatMarkdown($t('help.sections.dataAnalysisPage.executionPerspective.steps.interactWithAgent.title'))"></strong>
              <p>{{ $t('help.sections.dataAnalysisPage.executionPerspective.steps.interactWithAgent.description') }}</p>
              <p v-html="formatMarkdown($t('help.sections.dataAnalysisPage.executionPerspective.steps.interactWithAgent.examples.title'))"></p>
              <ul>
                <li v-for="(example, index) in getItems('help.sections.dataAnalysisPage.executionPerspective.steps.interactWithAgent.examples.items')" :key="index">{{ example }}</li>
              </ul>
              <p v-html="formatMarkdown($t('help.sections.dataAnalysisPage.executionPerspective.steps.interactWithAgent.agentProvides.title'))"></p>
              <ul>
                <li v-for="(item, index) in getItems('help.sections.dataAnalysisPage.executionPerspective.steps.interactWithAgent.agentProvides.items')" :key="index" v-html="formatMarkdown(item)"></li>
              </ul>
            </div>
            <div class="image-container">
              <img :src="getImagePath('data_analysis_execution.png')" :alt="$t('help.sections.dataAnalysisPage.executionPerspective.image')" />
              <p class="image-caption">{{ $t('help.sections.dataAnalysisPage.executionPerspective.image') }}</p>
            </div>
          </div>
        </section>

        <!-- 服务管理 -->
        <section id="service-management" class="help-section">
          <div class="section-header">
            <Icon name="analysis" size="lg" class="section-icon" />
            <h1>{{ $t('help.sections.serviceManagement.title') }}</h1>
          </div>
          <p class="section-description" v-html="formatMarkdown($t('help.sections.serviceManagement.description'))"></p>

          <div class="feature-card">
            <h2>{{ $t('help.sections.serviceManagement.serviceInfo.title') }}</h2>
            <p>{{ $t('help.sections.serviceManagement.serviceInfo.description') }}</p>
            <div class="info-box info-tip">
              <strong>{{ $t('help.sections.serviceManagement.serviceInfo.functions.title') }}</strong>
              <ul>
                <li v-for="(item, index) in getItems('help.sections.serviceManagement.serviceInfo.functions.items')" :key="index" v-html="formatMarkdown(item)"></li>
              </ul>
            </div>
            <div class="info-box info-tip">
              <strong>{{ $t('help.sections.serviceManagement.serviceInfo.useCases.title') }}</strong>
              <ul>
                <li v-for="(item, index) in getItems('help.sections.serviceManagement.serviceInfo.useCases.items')" :key="index" v-html="formatMarkdown(item)"></li>
              </ul>
            </div>
            <div class="info-box info-tip">
              <strong>{{ $t('help.sections.serviceManagement.serviceInfo.operations.title') }}</strong>
              <ul>
                <li v-for="(item, index) in getItems('help.sections.serviceManagement.serviceInfo.operations.items')" :key="index">{{ item }}</li>
              </ul>
            </div>
            <div class="info-box info-tip">
              <p v-html="formatMarkdown($t('help.sections.serviceManagement.serviceInfo.tip'))"></p>
            </div>
            <div class="image-container">
              <img :src="getImagePath('service_info_list.png')" :alt="$t('help.sections.serviceManagement.serviceInfo.images.list')" />
              <p class="image-caption">{{ $t('help.sections.serviceManagement.serviceInfo.images.list') }}</p>
            </div>
            <div class="image-container">
              <img :src="getImagePath('service_info_detail.png')" :alt="$t('help.sections.serviceManagement.serviceInfo.images.detail')" />
              <p class="image-caption">{{ $t('help.sections.serviceManagement.serviceInfo.images.detail') }}</p>
            </div>
          </div>

          <div class="feature-card">
            <h2>{{ $t('help.sections.serviceManagement.relationshipGraph.title') }}</h2>
            <p>{{ $t('help.sections.serviceManagement.relationshipGraph.description') }}</p>
            <div class="info-box info-tip">
              <strong>{{ $t('help.sections.serviceManagement.relationshipGraph.functions.components.title') }}</strong>
              <ul>
                <li v-for="(item, index) in getItems('help.sections.serviceManagement.relationshipGraph.functions.components.items')" :key="index" v-html="formatMarkdown(item)"></li>
              </ul>
            </div>
            <div class="info-box info-tip">
              <strong>{{ $t('help.sections.serviceManagement.relationshipGraph.interactions.title') }}</strong>
              <ul>
                <li v-for="(item, index) in getItems('help.sections.serviceManagement.relationshipGraph.interactions.items')" :key="index" v-html="formatMarkdown(item)"></li>
              </ul>
            </div>
            <div class="info-box info-tip">
              <strong>{{ $t('help.sections.serviceManagement.relationshipGraph.useCases.title') }}</strong>
              <ul>
                <li v-for="(item, index) in getItems('help.sections.serviceManagement.relationshipGraph.useCases.items')" :key="index" v-html="formatMarkdown(item)"></li>
              </ul>
            </div>
            <div class="info-box info-tip">
              <strong>{{ $t('help.sections.serviceManagement.relationshipGraph.tips.title') }}</strong>
              <ul>
                <li v-for="(item, index) in getItems('help.sections.serviceManagement.relationshipGraph.tips.items')" :key="index">{{ item }}</li>
              </ul>
            </div>
            <div class="info-box info-tip">
              <p v-html="formatMarkdown($t('help.sections.serviceManagement.relationshipGraph.tip'))"></p>
            </div>
            <div class="image-container">
              <img :src="getImagePath('relationship_graph_overview.png')" :alt="$t('help.sections.serviceManagement.relationshipGraph.images.overview')" />
              <p class="image-caption">{{ $t('help.sections.serviceManagement.relationshipGraph.images.overview') }}</p>
            </div>
            <div class="image-container">
              <img :src="getImagePath('relationship_graph_interaction.png')" :alt="$t('help.sections.serviceManagement.relationshipGraph.images.interaction')" />
              <p class="image-caption">{{ $t('help.sections.serviceManagement.relationshipGraph.images.interaction') }}</p>
            </div>
            <div class="image-container">
              <img :src="getImagePath('relationship_graph_path.png')" :alt="$t('help.sections.serviceManagement.relationshipGraph.images.path')" />
              <p class="image-caption">{{ $t('help.sections.serviceManagement.relationshipGraph.images.path') }}</p>
            </div>
          </div>
        </section>

        <!-- 执行管理 -->
        <section id="execution-management" class="help-section">
          <div class="section-header">
            <Icon name="analysis" size="lg" class="section-icon" />
            <h1>{{ $t('help.sections.executionManagement.title') }}</h1>
          </div>
          <p class="section-description" v-html="formatMarkdown($t('help.sections.executionManagement.description'))"></p>

          <div class="feature-card">
            <h2>{{ $t('help.sections.executionManagement.functions.title') }}</h2>
            <div class="info-box info-tip">
              <strong>{{ $t('help.sections.executionManagement.functions.executionList.title') }}</strong>
              <ul>
                <li v-for="(item, index) in getItems('help.sections.executionManagement.functions.executionList.items')" :key="index" v-html="formatMarkdown(item)"></li>
              </ul>
            </div>
            <div class="info-box info-tip">
              <strong>{{ $t('help.sections.executionManagement.functions.executionDetails.title') }}</strong>
              <ul>
                <li v-for="(item, index) in getItems('help.sections.executionManagement.functions.executionDetails.items')" :key="index" v-html="formatMarkdown(item)"></li>
              </ul>
            </div>
            <div class="image-container">
              <img :src="getImagePath('execution_management_list.png')" :alt="$t('help.sections.executionManagement.functions.images.list')" />
              <p class="image-caption">{{ $t('help.sections.executionManagement.functions.images.list') }}</p>
            </div>
            <div class="image-container">
              <img :src="getImagePath('execution_management_detail.png')" :alt="$t('help.sections.executionManagement.functions.images.detail')" />
              <p class="image-caption">{{ $t('help.sections.executionManagement.functions.images.detail') }}</p>
            </div>
          </div>
        </section>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import Icon from './common/Icon.vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'

// 配置 marked 选项，确保能够正确解析列表
marked.setOptions({
  breaks: true, // 支持 GitHub 风格的换行
  gfm: true, // 启用 GitHub Flavored Markdown
})

const { t, messages, locale } = useI18n()
const contentRef = ref<HTMLElement | null>(null)
const activeSection = ref('introduction')

const sections = computed(() => [
  { id: 'introduction', title: t('help.introduction.title'), icon: 'info' },
  { id: 'getting-started', title: t('help.sections.gettingStarted.title'), icon: 'rocket' },
  { id: 'analysis-page', title: t('help.sections.analysisPage.title'), icon: 'analysis' },
  { id: 'data-analysis-page', title: t('help.sections.dataAnalysisPage.title'), icon: 'visualization' },
  { id: 'service-management', title: t('help.sections.serviceManagement.title'), icon: 'analysis' },
  { id: 'execution-management', title: t('help.sections.executionManagement.title'), icon: 'analysis' }
])

/**
 * 获取图片路径
 * 使用 import.meta.env.BASE_URL 来支持 Vite 的 base 配置
 */
function getImagePath(imageName: string): string {
  // import.meta.env.BASE_URL 在开发环境通常是 '/'，在生产环境是 '/STA-MAS/'
  // 移除末尾的斜杠（如果有），然后拼接路径
  const base = import.meta.env.BASE_URL.replace(/\/$/, '')
  return `${base}/pictures/${imageName}`
}

/**
 * 格式化 Markdown 文本
 */
function formatMarkdown(text: string): string {
  // 类型检查：确保传入的是字符串
  if (typeof text !== 'string') {
    console.warn('formatMarkdown received non-string value:', typeof text, text)
    return ''
  }
  if (!text) return ''
  
  // 处理包含列表语法的文本
  // 检测文本是否以列表项开头（可能前面有空格）
  // 匹配模式：可选的前导空格 + 列表标记（-、*、+ 或数字.）+ 空格 + 内容
  // 使用多行模式，但只匹配第一行
  const trimmedText = text.trimStart()
  const listItemMatch = trimmedText.match(/^([-*+]|\d+\.)\s+(.+)$/s)
  
  if (listItemMatch) {
    const [, marker, content] = listItemMatch
    // 去掉前导空格，使用标准的 markdown 列表格式
    // 对于无序列表，直接使用 "- item" 格式
    // 对于有序列表，使用 "1. item" 格式
    const isOrdered = /^\d+\.$/.test(marker)
    const processedText = isOrdered ? `${marker} ${content.trim()}` : `- ${content.trim()}`
    const parsed = marked.parse(processedText) as string
    
    // 提取 <li> 内的内容（因为外层已经有 <li> 标签了，不需要再生成列表结构）
    // 匹配 <ul><li>...</li></ul> 或 <ol><li>...</li></ol> 结构（可能包含换行）
    const listMatch = parsed.match(/<(?:ul|ol)>\s*<li>(.*?)<\/li>\s*<\/(?:ul|ol)>/s)
    if (listMatch) {
      // 如果 marked 生成了列表结构，提取 <li> 内的内容
      return DOMPurify.sanitize(listMatch[1].trim())
    }
    
    // 如果 marked 没有生成列表结构（只生成了段落），提取段落内容
    const pMatch = parsed.match(/<p>(.*?)<\/p>/s)
    if (pMatch) {
      return DOMPurify.sanitize(pMatch[1])
    }
    
    // 如果都没有匹配到，直接返回解析结果（去除可能的 <p> 标签）
    return DOMPurify.sanitize(parsed.replace(/<\/?p>/g, ''))
  }
  
  // 对于其他文本，直接解析
  return DOMPurify.sanitize(marked.parse(text) as string)
}

/**
 * 获取步骤列表（处理数组或对象）
 */
function getSteps(key: string): string[] {
  try {
    // 从 messages 中获取数组
    const currentMessages = messages.value[locale.value] as any
    if (!currentMessages) {
      console.warn(`No messages found for locale: ${locale.value}`)
      return []
    }
    
    // 按路径分割键并访问嵌套对象
    const keys = key.split('.')
    let value: any = currentMessages
    for (const k of keys) {
      if (value && typeof value === 'object' && k in value) {
        value = value[k]
      } else {
      console.warn(`Translation key not found: ${key}`)
      return []
    }
    }
    
    if (Array.isArray(value)) {
      return value.filter(step => typeof step === 'string') // 确保只返回字符串数组
    }
    
    console.warn(`Translation key ${key} is not an array:`, typeof value)
    return []
  } catch (error) {
    console.error(`Error getting steps for key ${key}:`, error)
    return []
  }
}

/**
 * 获取 items 数组（安全处理）
 */
function getItems(key: string): string[] {
  try {
    // 从 messages 中获取数组
    const currentMessages = messages.value[locale.value] as any
    if (!currentMessages) {
      console.warn(`No messages found for locale: ${locale.value}`)
      return []
    }
    
    // 按路径分割键并访问嵌套对象
    const keys = key.split('.')
    let value: any = currentMessages
    for (const k of keys) {
      if (value && typeof value === 'object' && k in value) {
        value = value[k]
      } else {
      console.warn(`Translation key not found: ${key}`)
      return []
    }
    }
    
    if (Array.isArray(value)) {
      return value.filter(item => typeof item === 'string') // 确保只返回字符串数组
    }
    
    console.warn(`Translation key ${key} is not an array:`, typeof value)
    return []
  } catch (error) {
    console.error(`Error getting items for key ${key}:`, error)
    return []
  }
}

/**
 * 滚动到指定章节
 */
function scrollToSection(sectionId: string) {
  const element = document.getElementById(sectionId)
  if (element) {
    element.scrollIntoView({ behavior: 'smooth', block: 'start' })
    activeSection.value = sectionId
  }
}

/**
 * 监听滚动，更新活动章节
 */
function handleScroll() {
  if (!contentRef.value) return

  const sections = contentRef.value.querySelectorAll('.help-section')
  const scrollTop = contentRef.value.scrollTop
  const offset = 100

  for (let i = sections.length - 1; i >= 0; i--) {
    const section = sections[i] as HTMLElement
    if (section.offsetTop - offset <= scrollTop) {
      activeSection.value = section.id
      break
    }
  }
}

onMounted(() => {
  if (contentRef.value) {
    contentRef.value.addEventListener('scroll', handleScroll)
  }
})

onUnmounted(() => {
  if (contentRef.value) {
    contentRef.value.removeEventListener('scroll', handleScroll)
  }
})
</script>

<style scoped>
.help-page {
  width: 100%;
  height: 100%;
  overflow: hidden;
  background: var(--bg-primary, #ffffff);
}

.help-container {
  display: flex;
  height: 100%;
  max-width: 1600px;
  margin: 0 auto;
}

/* 侧边栏样式 */
.help-sidebar {
  width: 300px;
  flex-shrink: 0;
  background: linear-gradient(180deg, #fafbfc 0%, #f5f7fa 100%);
  border-right: 1px solid var(--border-color, #e0e0e0);
  overflow-y: auto;
  padding: 2rem 0;
  box-shadow: 2px 0 8px rgba(0, 0, 0, 0.04);
}

.sidebar-header {
  padding: 0 1.5rem 1.5rem;
  border-bottom: 1px solid var(--border-color, #e0e0e0);
  margin-bottom: 1.5rem;
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.header-icon {
  color: var(--accent-primary, #1890ff);
}

.sidebar-header h2 {
  margin: 0;
  font-size: 1.5rem;
  font-weight: 600;
  color: var(--text-primary, #333);
}

.sidebar-nav {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  padding: 0 1rem;
}

.nav-link {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.875rem 1rem;
  border-radius: 8px;
  text-decoration: none;
  color: var(--text-secondary, #666);
  font-size: 0.95rem;
  transition: all 0.2s ease;
  font-weight: 500;
}

.nav-link:hover {
  background: rgba(24, 144, 255, 0.08);
  color: var(--accent-primary, #1890ff);
  transform: translateX(4px);
}

.nav-link.active {
  background: linear-gradient(90deg, rgba(24, 144, 255, 0.15) 0%, rgba(24, 144, 255, 0.08) 100%);
  color: var(--accent-primary, #1890ff);
  border-left: 3px solid var(--accent-primary, #1890ff);
  font-weight: 600;
}

.nav-icon {
  flex-shrink: 0;
}

/* 主内容区域样式 */
.help-content {
  flex: 1;
  overflow-y: auto;
  padding: 3rem 4rem;
  background: var(--bg-primary, #ffffff);
}

.help-section {
  margin-bottom: 5rem;
  scroll-margin-top: 2rem;
}

.section-header {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-bottom: 1.5rem;
  padding-bottom: 1rem;
  border-bottom: 3px solid var(--accent-primary, #1890ff);
}

.section-icon {
  color: var(--accent-primary, #1890ff);
}

.help-section h1 {
  font-size: 2.25rem;
  font-weight: 700;
  color: var(--text-primary, #333);
  margin: 0;
  letter-spacing: -0.02em;
}

.section-description {
  font-size: 1.125rem;
  line-height: 1.8;
  color: var(--text-secondary, #666);
  margin-bottom: 2rem;
}

.help-section h2 {
  font-size: 1.75rem;
  font-weight: 600;
  color: var(--text-primary, #333);
  margin: 2.5rem 0 1.25rem 0;
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.feature-icon {
  color: var(--accent-primary, #1890ff);
}

.help-section h3 {
  font-size: 1.375rem;
  font-weight: 600;
  color: var(--text-primary, #333);
  margin: 2rem 0 1rem 0;
}

.help-section p {
  line-height: 1.8;
  color: var(--text-secondary, #666);
  margin-bottom: 1rem;
  font-size: 1rem;
}

.help-section ul,
.help-section ol {
  margin: 1.25rem 0;
  padding-left: 2rem;
  line-height: 1.8;
  color: var(--text-secondary, #666);
}

.help-section li {
  margin-bottom: 0.75rem;
}

/* 功能卡片 */
.feature-card {
  background: linear-gradient(180deg, #ffffff 0%, #fafbfc 100%);
  border: 1px solid var(--border-color, #e0e0e0);
  border-radius: 12px;
  padding: 2rem;
  margin: 2rem 0;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
  transition: all 0.3s ease;
}

.feature-card:hover {
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08);
  transform: translateY(-2px);
}

.feature-list {
  list-style: none;
  padding-left: 0;
}

.feature-list li {
  padding-left: 1.5rem;
  position: relative;
  margin-bottom: 0.75rem;
}

.feature-list li::before {
  content: "•";
  position: absolute;
  left: 0;
  color: var(--accent-primary, #1890ff);
  font-weight: bold;
}

.step-list {
  list-style: none;
  padding-left: 0;
  counter-reset: step-counter;
}

.step-list li {
  counter-increment: step-counter;
  position: relative;
  padding-left: 3rem;
  margin-bottom: 2rem;
  padding-bottom: 1.5rem;
  border-bottom: 1px solid var(--border-color, #e0e0e0);
}

.step-list li:last-child {
  border-bottom: none;
}

.step-list li::before {
  content: counter(step-counter);
  position: absolute;
  left: 0;
  top: 0;
  width: 2rem;
  height: 2rem;
  background: linear-gradient(135deg, var(--accent-primary, #1890ff) 0%, #40a9ff 100%);
  color: white;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-size: 0.875rem;
  box-shadow: 0 2px 8px rgba(24, 144, 255, 0.3);
}

.step-list li strong {
  display: block;
  color: var(--text-primary, #333);
  font-size: 1.125rem;
  margin-bottom: 0.5rem;
  font-weight: 600;
}

.step-list li p {
  margin: 0.5rem 0;
  color: var(--text-secondary, #666);
}

/* 信息框 */
.info-box {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  padding: 1.25rem 1.75rem;
  border-radius: 8px;
  margin: 1.5rem 0;
  border-left: 4px solid;
}

.info-tip {
  background: rgba(24, 144, 255, 0.08);
  border-left-color: var(--accent-primary, #1890ff);
}

.info-warning {
  background: rgba(255, 193, 7, 0.1);
  border-left-color: #ffc107;
}

.info-box strong {
  display: block;
  margin-bottom: 0.5rem;
  color: var(--text-primary, #333);
  font-weight: 600;
}

.info-box p {
  margin: 0;
  color: var(--text-secondary, #666);
}

.info-box ul {
  margin: 0.5rem 0;
  padding-left: 1.5rem;
}

.info-box ol {
  margin: 0.5rem 0;
  padding-left: 1.5rem;
}

/* 图片容器 */
.image-container {
  margin: 2rem 0;
  text-align: center;
}

.image-container img {
  max-width: 100%;
  height: auto;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  border: 1px solid var(--border-color, #e0e0e0);
}

.image-caption {
  margin-top: 0.75rem;
  font-size: 0.9rem;
  color: var(--text-secondary, #666);
  font-style: italic;
}

.image-example {
  margin-top: 0.75rem;
  margin-left: 0;
  margin-right: 0;
  padding: 0.75rem 1rem;
  border-left: 4px solid var(--accent-primary, #1890ff);
  background: rgba(24, 144, 255, 0.05);
  color: var(--text-secondary, #666);
  font-size: 0.9rem;
  font-style: normal;
}

.image-example strong {
  color: var(--text-primary, #333);
  font-weight: 600;
}

/* 代码示例 */
.code-example {
  background: #1e1e1e;
  border-radius: 8px;
  padding: 1.5rem;
  margin: 1.5rem 0;
  overflow-x: auto;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.code-label {
  color: #858585;
  font-size: 0.875rem;
  margin-bottom: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.code-example pre {
  margin: 0;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', 'Consolas', monospace;
  font-size: 0.9rem;
  line-height: 1.6;
  color: #d4d4d4;
}

.code-example code {
  font-family: inherit;
}

.help-section code {
  background: rgba(24, 144, 255, 0.1);
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  font-size: 0.9em;
  color: var(--accent-primary, #1890ff);
  font-weight: 500;
}

/* 响应式设计 */
@media (max-width: 1200px) {
  .help-content {
    padding: 2rem 3rem;
  }
}

@media (max-width: 768px) {
  .help-container {
    flex-direction: column;
  }

  .help-sidebar {
    width: 100%;
    border-right: none;
    border-bottom: 1px solid var(--border-color, #e0e0e0);
    max-height: 300px;
  }

  .help-content {
    padding: 1.5rem;
  }

  .feature-card {
    padding: 1.5rem;
  }
}
</style>
