/**
 * Displays a review with discussion on the review request page.
 *
 * Review boxes contain discussion on parts of a review request. This includes
 * comments, screenshots, and file attachments.
 */
RB.ReviewBoxView = RB.CollapsableBoxView.extend({
    /**
     * Initialize the view.
     *
     * Args:
     *     options (object):
     *         Options for the view.
     *
     * Option Args:
     *     reviewRequestEditor (RB.ReviewRequestEditor):
     *         The review request editor.
     *
     *     showSendEmail (boolean):
     *         Whether to show the "Send E-mail" box on replies.
     */
    initialize(options) {
        RB.CollapsableBoxView.prototype.initialize.call(this, options);

        this._reviewView = null;
        this._draftBannerShown = false;
        this._$boxStatus = null;
        this._$fixItLabel = null;
    },

    /**
     * Render the review box.
     *
     * This will prepare a reply draft banner, used if the user is replying
     * to any comments on the review.
     *
     * Each comment section will be set up to allow discussion.
     *
     * Returns:
     *     RB.ReviewBoxView:
     *     This object, for chaining.
     */
    render() {
        RB.CollapsableBoxView.prototype.render.call(this);

        this._reviewView = new RB.ReviewView({
            el: this.el,
            model: this.model,
            reviewRequestEditor: this.options.reviewRequestEditor,
            $bannerFloatContainer: this._$box,
            $bannerParent: this.$('.banners'),
            bannerNoFloatContainerClass: 'collapsed',
            showSendEmail: this.options.showSendEmail,
        });

        this._$boxStatus = this.$('.box-status');
        this._$fixItLabel = this._$boxStatus.find('.fix-it-label');

        this.listenTo(this._reviewView, 'hasDraftChanged',
                      hasDraft => this.$el.toggleClass('has-draft', hasDraft));
        this.listenTo(this._reviewView, 'openIssuesChanged',
                      this._updateLabels);

        this._reviewView.render();
        this._updateLabels();

        return this;
    },

    /**
     * Return the ReviewReplyEditorView with the given context type and ID.
     *
     * Args:
     *     contextType (string):
     *         The type of object being replied to (such as ``body_top`` or
     *         ``diff_comments``)
     *
     *     contextID (number, optional):
     *         The ID of the comment being replied to, if appropriate.
     *
     * Returns:
     *     RB.ReviewReplyEditorView:
     *     The matching editor view.
     */
    getReviewReplyEditorView(contextType, contextID) {
        return this._reviewView.getReviewReplyEditorView(contextType,
                                                         contextID);
    },

    /**
     * Update the "Ship It" and "Fix It" labels based on the open issue counts.
     *
     * If there are open issues, there will be a "Fix it!" label.
     *
     * If there's a Ship It, there will be a "Ship it!" label.
     *
     * If there's both a Ship It and open issues, the "Fix it!" label will
     * be shown overlaid on top of the "Ship it!" label, and will go away
     * once the issues are resolved.
     */
    _updateLabels() {
        if (this._reviewView.hasOpenIssues()) {
            this._$boxStatus.addClass('has-issues');
            this._$fixItLabel
                .show()
                .css({
                    opacity: 1,
                    left: 0,
                });
        } else {
            this._$fixItLabel.css({
                opacity: 0,
                left: '-100px',
            });
            this._$boxStatus.removeClass('has-issues');
        }
    },
});
