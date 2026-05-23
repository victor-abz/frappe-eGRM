// ---------------------------------------------------------------------------
// Step 2 — Administrative Levels & Regions (composite of Levels + Regions tabs)
// ---------------------------------------------------------------------------
class GRMWizardStep2AdminUnits {
    constructor($body, project, wizard) {
        this.$body = $body;
        this.project = project;
        this.wizard = wizard;
        this.render();
    }

    render() {
        if (!this.project) {
            this.$body.html(`
                <div class="grm-wizard-placeholder">
                  <p class="text-muted">${__("Save Step 1 first to create the project.")}</p>
                </div>
            `);
            return;
        }
        this.$body.html(`
            <div class="grm-step2-admin">
              <ul class="nav nav-tabs" role="tablist">
                <li class="nav-item"><a class="nav-link active" data-toggle="tab" href="#grm-tab-levels">${__("Levels")}</a></li>
                <li class="nav-item"><a class="nav-link" data-toggle="tab" href="#grm-tab-regions">${__("Regions")}</a></li>
              </ul>
              <div class="tab-content pt-3">
                <div class="tab-pane fade show active" id="grm-tab-levels"></div>
                <div class="tab-pane fade" id="grm-tab-regions"></div>
              </div>
            </div>
        `);
        this.levels_inner = new GRMWizardStep2AdminLevelsInner(this.$body.find("#grm-tab-levels"), this.project, this.wizard);
        this.regions_inner = new GRMWizardStep2AdminRegionsInner(this.$body.find("#grm-tab-regions"), this.project, this.wizard);
    }

    async save() {
        if (!this.levels_inner) return true;
        const ok1 = await this.levels_inner.save();
        if (!ok1) return false;
        if (this.regions_inner) {
            return this.regions_inner.save();
        }
        return true;
    }
}

