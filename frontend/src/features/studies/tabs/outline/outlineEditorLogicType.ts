import type { Logic } from "kea"

import type { GuideSection, SectionRandomizationMode } from "./outlineEditorLogic"

export interface outlineEditorLogicType extends Logic {
    actionCreators: Record<string, any>
    actionKeys: Record<string, string>
    actionTypes: Record<string, string>
    actions: Record<string, any>
    asyncActions: Record<string, any>
    defaults: {
        sections: GuideSection[]
        selectedSectionId: string | null
        selectedQuestionId: string | null
        sectionRandomizationEnabled: boolean
        sectionRandomizationMode: SectionRandomizationMode
        loadedGuideId: string | null
        loadedGuideVersion: string
        loadedGuideLanguage: string
        draftRevision: number
        savedRevision: number
        isLoadingGuide: boolean
        isSavingGuide: boolean
        guideError: string | null
        autosaveQueued: boolean
    }
    events: {}
    key: undefined
    listeners: Record<string, any>
    path: ["features", "studies", "tabs", "outline", "outlineEditorLogic"]
    pathString: "features.studies.tabs.outline.outlineEditorLogic"
    props: Record<string, unknown>
    reducer: (state: any, action: any, fullState: any) => {
        sections: GuideSection[]
        selectedSectionId: string | null
        selectedQuestionId: string | null
        sectionRandomizationEnabled: boolean
        sectionRandomizationMode: SectionRandomizationMode
        loadedGuideId: string | null
        loadedGuideVersion: string
        loadedGuideLanguage: string
        draftRevision: number
        savedRevision: number
        isLoadingGuide: boolean
        isSavingGuide: boolean
        guideError: string | null
        autosaveQueued: boolean
    }
    reducers: {
        sections: (state: GuideSection[], action: any, fullState: any) => GuideSection[]
        selectedSectionId: (state: string | null, action: any, fullState: any) => string | null
        selectedQuestionId: (state: string | null, action: any, fullState: any) => string | null
        sectionRandomizationEnabled: (state: boolean, action: any, fullState: any) => boolean
        sectionRandomizationMode: (
            state: SectionRandomizationMode,
            action: any,
            fullState: any,
        ) => SectionRandomizationMode
        loadedGuideId: (state: string | null, action: any, fullState: any) => string | null
        loadedGuideVersion: (state: string, action: any, fullState: any) => string
        loadedGuideLanguage: (state: string, action: any, fullState: any) => string
        draftRevision: (state: number, action: any, fullState: any) => number
        savedRevision: (state: number, action: any, fullState: any) => number
        isLoadingGuide: (state: boolean, action: any, fullState: any) => boolean
        isSavingGuide: (state: boolean, action: any, fullState: any) => boolean
        guideError: (state: string | null, action: any, fullState: any) => string | null
        autosaveQueued: (state: boolean, action: any, fullState: any) => boolean
    }
    selector: (state: any) => {
        sections: GuideSection[]
        selectedSectionId: string | null
        selectedQuestionId: string | null
        sectionRandomizationEnabled: boolean
        sectionRandomizationMode: SectionRandomizationMode
        studyId: string | null
        loadedGuideId: string | null
        loadedGuideVersion: string
        loadedGuideLanguage: string
        draftRevision: number
        savedRevision: number
        isLoadingGuide: boolean
        isSavingGuide: boolean
        guideError: string | null
        autosaveQueued: boolean
    }
    selectors: Record<string, any>
    sharedListeners: Record<string, any>
    values: {
        sections: GuideSection[]
        selectedSectionId: string | null
        selectedQuestionId: string | null
        sectionRandomizationEnabled: boolean
        sectionRandomizationMode: SectionRandomizationMode
        studyId: string | null
        loadedGuideId: string | null
        loadedGuideVersion: string
        loadedGuideLanguage: string
        draftRevision: number
        savedRevision: number
        isLoadingGuide: boolean
        isSavingGuide: boolean
        guideError: string | null
        autosaveQueued: boolean
    }
    _isKea: true
    _isKeaWithKey: false
}
