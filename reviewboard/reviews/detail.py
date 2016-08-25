"""Definitions for the review request detail view."""

from __future__ import unicode_literals

from collections import defaultdict
from datetime import datetime

from django.db.models import Q
from django.utils import six
from django.utils.timezone import utc

from reviewboard.reviews.builtin_fields import ReviewRequestPageDataMixin
from reviewboard.reviews.fields import get_review_request_fieldsets
from reviewboard.reviews.models import (BaseComment,
                                        Comment,
                                        FileAttachmentComment,
                                        GeneralComment,
                                        ReviewRequest,
                                        ScreenshotComment)


class ReviewRequestPageData(object):
    """Data for the review request page.

    The review request detail page needs a lot of data from the database, and
    going through the standard model relations will result in a lot more
    queries than necessary. This class bundles all that data together and
    handles pre-fetching and re-associating as necessary to limit the required
    number of queries.

    All of the attributes within the class may not be available until both
    :py:meth:`query_data_pre_etag` and :py:meth:`query_data_post_etag` are
    called.

    This object is not meant to be public API, and may change at any time. You
    should not use it in extension code.

    Attributes:
        body_bottom_replies (dict):
            A mapping from a top-level review ID to a list of the
            :py:class:`reviewboard.reviews.models.Review` objects which reply
            to it.

        body_top_replies (dict):
            A mapping from a top-level review ID to a list of the
            :py:class:`reviewboard.reviews.models.Review` objects which reply
            to it.

        comments (list):
            A list of all comments associated with all reviews shown on the
            page.

        changedescs (list of reviewboard.changedescs.models.ChangeDescription):
            All the change descriptions to be shown on the page.

        diffsets (list of reviewboard.diffviewer.models.DiffSet):
            All of the diffsets associated with the review request.

        diffsets_by_id (dict):
            A mapping from ID to
            :py:class:`reviewboard.diffviewer.models.DiffSet`.

        draft (reviewboard.reviews.models.ReviewRequestDraft):
            The active draft of the review request, if any. May be ``None``.

        active file_attachments (list of reviewboard.attachments.models.FileAttachment):
            All the active file attachments associated with the review request.

        all_file_attachments (list of reviewboard.attachments.models.FileAttachment):
            All the file attachments associated with the review request.

        file_attachments_by_id (dict):
            A mapping from ID to
            :py:class:`reviewboard.attachments.models.FileAttachment`

        issues (dict):
            A dictionary storing counts of the various issue states throughout
            the page.

        latest_changedesc_timestamp (datetime.datetime):
            The timestamp of the most recent change description on the page.

        latest_review_timestamp (datetime.datetime):
            The timestamp of the most recent review on the page.

        latest_timestamps_by_review_id (dict):
            A mapping from top-level review ID to the latest timestamp of the
            thread.

        review_request (reviewboard.reviews.models.ReviewRequest):
            The review request.

        review_request_details (reviewboard.reviews.models.base_review_request_details.BaseReviewRequestDetails):
            The review request (or the active draft thereof). In practice this
            will either be a
            :py:class:`reviewboard.reviews.models.ReviewRequest` or a
            :py:class:`reviewboard.reviews.models.ReviewRequestDraft`.

        reviews (list of reviewboard.reviews.models.Review):
            All the reviews to be shown on the page. This includes any draft
            reviews owned by the requesting user but not drafts owned by
            others.

        reviews_by_id (dict):
            A mapping from ID to :py:class:`reviewboard.reviews.models.Review`.

        active_screenshots (list of reviewboard.reviews.models.Screenshot):
            All the active screenshots associated with the review request.

        all_screenshots (list of reviewboard.reviews.models.Screenshot):
            All the screenshots associated with the review request.

        screenshots_by_id (dict):
            A mapping from ID to
            :py:class:`reviewboard.reviews.models.Screenshot`.
    """  # noqa

    def __init__(self, review_request, request):
        """Initialize the data object.

        Args:
            review_request (reviewboard.reviews.models.ReviewRequest):
                The review request.

            request (django.http.HttpRequest):
                The HTTP request object.
        """
        self.review_request = review_request
        self.request = request

    def query_data_pre_etag(self):
        """Perform initial queries for the page.

        This method will populate only the data needed to compute the ETag. We
        avoid everything else until later so as to do the minimum amount
        possible before reporting to the client that they can just use their
        cached copy.
        """
        # Query for all the reviews that should be shown on the page (either
        # ones which are public or draft reviews owned by the current user).
        reviews_query = Q(public=True)

        if self.request.user.is_authenticated():
            reviews_query |= Q(user_id=self.request.user.pk)

        self.reviews = list(
            self.review_request.reviews
            .filter(reviews_query)
            .order_by('-timestamp')
            .select_related('user')
        )

        if len(self.reviews) == 0:
            self.latest_review_timestamp = datetime.fromtimestamp(0, utc)
        else:
            self.latest_review_timestamp = self.reviews[0].timestamp

        # Get all the public ChangeDescriptions.
        self.changedescs = list(
            self.review_request.changedescs.filter(public=True))

        if len(self.changedescs) == 0:
            self.latest_changedesc_timestamp = datetime.fromtimestamp(0, utc)
        else:
            self.latest_changedesc_timestamp = self.changedescs[0].timestamp

        # Get the active draft (if any).
        self.draft = self.review_request.get_draft(self.request.user)

        # Get diffsets.
        self.diffsets = self.review_request.get_diffsets()
        self.diffsets_by_id = self._build_id_map(self.diffsets)

    def query_data_post_etag(self):
        """Perform remaining queries for the page.

        This method will populate everything else needed for the display of the
        review request page other than that which was required to compute the
        ETag.
        """
        self.reviews_by_id = self._build_id_map(self.reviews)

        self.body_top_replies = defaultdict(list)
        self.body_bottom_replies = defaultdict(list)
        self.latest_timestamps_by_review_id = defaultdict(lambda: 0)

        for r in self.reviews:
            r._body_top_replies = []
            r._body_bottom_replies = []

            if r.body_top_reply_to_id is not None:
                self.body_top_replies[r.body_top_reply_to_id].append(r)

            if r.body_bottom_reply_to_id is not None:
                self.body_bottom_replies[r.body_bottom_reply_to_id].append(r)

            # Find the latest reply timestamp for each top-level review.
            parent_id = r.base_reply_to_id

            if parent_id is not None:
                self.latest_timestamps_by_review_id[parent_id] = max(
                    r.timestamp.replace(tzinfo=utc).ctime(),
                    self.latest_timestamps_by_review_id[parent_id])

        # Link up all the review body replies.
        for reply_id, replies in six.iteritems(self.body_top_replies):
            self.reviews_by_id[reply_id]._body_top_replies = reversed(replies)

        for reply_id, replies in six.iteritems(self.body_bottom_replies):
            self.reviews_by_id[reply_id]._body_bottom_replies = \
                reversed(replies)

        self.review_request_details = self.draft or self.review_request

        # Get all the file attachments and screenshots.
        #
        # Note that we fetch both active and inactive file attachments and
        # screenshots. We do this because even though they've been removed,
        # they still will be rendered in change descriptions.
        self.active_file_attachments = \
            list(self.review_request_details.get_file_attachments())
        self.all_file_attachments = (
            self.active_file_attachments +
            list(self.review_request_details.get_inactive_file_attachments()))
        self.file_attachments_by_id = \
            self._build_id_map(self.all_file_attachments)

        for attachment in self.all_file_attachments:
            attachment._comments = []

        self.active_screenshots = \
            list(self.review_request_details.get_screenshots())
        self.all_screenshots = (
            self.active_screenshots +
            list(self.review_request_details.get_inactive_screenshots()))
        self.screenshots_by_id = self._build_id_map(self.all_screenshots)

        for screenshot in self.all_screenshots:
            screenshot._comments = []

        # Get all the comments and attach them to the reviews
        review_ids = self.reviews_by_id.keys()

        self.comments = []
        self.issues = {
            'total': 0,
            'open': 0,
            'resolved': 0,
            'dropped': 0,
        }

        for model, key, ordering in (
            (Comment, 'diff_comments', ('comment__filediff',
                                        'comment__first_line',
                                        'comment__timestamp')),
            (ScreenshotComment, 'screenshot_comments', None),
            (FileAttachmentComment, 'file_attachment_comments', None),
            (GeneralComment, 'general_comments', None)):
            # Due to mistakes in how we initially made the schema, we have a
            # ManyToManyField in between comments and reviews, instead of
            # comments having a ForeignKey to the review. This makes it
            # difficult to easily go from a comment to a review ID.
            #
            # The solution to this is to not query the comment objects, but
            # rather the through table. This will let us grab the review and
            # comment in one go, using select_related.
            related_field = model.review.related.field
            comment_field_name = related_field.m2m_reverse_field_name()
            through = related_field.rel.through
            q = through.objects.filter(review__in=review_ids).select_related()

            if ordering:
                q = q.order_by(*ordering)

            objs = list(q)

            # We do two passes. One to build a mapping, and one to actually
            # process comments.
            comment_map = {}

            for obj in objs:
                comment = getattr(obj, comment_field_name)
                comment._type = key
                comment._replies = []
                comment_map[comment.pk] = comment

            for obj in objs:
                comment = getattr(obj, comment_field_name)

                self.comments.append(comment)

                # Short-circuit some object fetches for the comment by setting
                # some internal state on them.
                assert obj.review_id in self.reviews_by_id
                review = self.reviews_by_id[obj.review_id]
                comment._review = review
                comment._review_request = self.review_request

                # If the comment has an associated object (such as a file
                # attachment) that we've already fetched, attach it to prevent
                # future queries.
                if isinstance(comment, FileAttachmentComment):
                    attachment_id = comment.file_attachment_id
                    f = self.file_attachments_by_id[attachment_id]
                    comment.file_attachment = f
                    f._comments.append(comment)

                    diff_against_id = comment.diff_against_file_attachment_id

                    if diff_against_id is not None:
                        f = self.file_attachments_by_id[diff_against_id]
                        comment.diff_against_file_attachment = f
                elif isinstance(comment, ScreenshotComment):
                    screenshot = self.screenshots_by_id[comment.screenshot_id]
                    comment.screenshot = screenshot
                    screenshot._comments.append(comment)

                # We've hit legacy database cases where there were entries that
                # weren't a reply, and were just orphaned. Ignore them.
                if review.is_reply() and comment.is_reply():
                    replied_comment = comment_map[comment.reply_to_id]
                    replied_comment._replies.append(comment)

                if review.public and comment.issue_opened:
                    status_key = \
                        comment.issue_status_to_string(comment.issue_status)
                    self.issues[status_key] += 1
                    self.issues['total'] += 1

    def _build_id_map(self, objects):
        """Return an ID map from a list of objects.

        Args:
            objects (list):
                A list of objects queried via django.

        Returns:
            dict:
            A dictionary mapping each ID to the resulting object.
        """
        return {
            obj.pk: obj
            for obj in objects
        }


class BaseReviewRequestPageEntry(object):
    """An entry on the review detail page.

    This contains backend logic and frontend templates for one of the boxes
    that appears below the main review request box on the review request detail
    page.

    Attributes:
        timestamp (datetime.datetime):
            The timestamp of the entry.

        collasped (bool):
            Whether the entry should be initially collapsed.
    """

    #: The template to render for the HTML.
    template_name = None

    #: The template to render for any JavaScript.
    js_template_name = None

    def __init__(self, timestamp, collapsed):
        """Initialize the entry.

        Args:
            timestamp (datetime.datetime):
                The timestamp of the entry.

            collapsed (bool):
                Whether the entry is collapsed by default.
        """
        self.timestamp = timestamp
        self.collapsed = collapsed


class ReviewEntry(BaseReviewRequestPageEntry):
    """A review box.

    Attributes:
        review (reviewboard.reviews.models.Review):
            The review for this entry.

        issue_open_count (int):
            The count of open issues within this review.

        has_issues (bool):
            Whether there are any issues (open or not).

        comments (dict):
            A dictionary of comments. Each key in this represents a comment
            type, and the values are lists of comment objects.
    """

    template_name = 'reviews/boxes/review.html'
    js_template_name = 'reviews/boxes/review.js'

    def __init__(self, request, review_request, review, collapsed, data):
        """Initialize the entry.

        Args:
            request (django.http.HttpRequest):
                The request object.

            review_request (reviewboard.reviews.models.ReviewRequest):
                The review request that the change is for.

            review (reviewboard.reviews.models.Review):
                The review.

            collapsed (bool):
                Whether the entry is collapsed by default.

            data (ReviewRequestPageData):
                Pre-queried data for the review request page.
        """
        super(ReviewEntry, self).__init__(review.timestamp, collapsed)

        self.request = request
        self.review_request = review_request
        self.review = review
        self.issue_open_count = 0
        self.has_issues = False
        self.comments = {
            'diff_comments': [],
            'screenshot_comments': [],
            'file_attachment_comments': [],
            'general_comments': [],
        }

    def add_comment(self, comment_type, comment):
        """Add a comment to this entry.

        Args:
            comment_type (unicode):
                The type of comment (an index into the :py:attr:`comments`
                dictionary).

            comment (reviewboard.reviews.models.BaseComment):
                The comment to add.
        """
        self.comments[comment_type].append(comment)

        if comment.issue_opened:
            self.has_issues = True

            if comment.issue_status == BaseComment.OPEN:
                self.issue_open_count += 1

                if self.review_request.submitter == self.request.user:
                    self.collapsed = False


class ChangeEntry(BaseReviewRequestPageEntry):
    """A change description box.

    Attributes:
        changedesc (reviewboard.changedescs.models.ChangeDescription):
            The change description for this entry.
    """

    template_name = 'reviews/boxes/change.html'
    js_template_name = 'reviews/boxes/change.js'

    def __init__(self, request, review_request, changedesc, collapsed, data):
        """Initialize the entry.

        Args:
            request (django.http.HttpRequest):
                The request object.

            review_request (reviewboard.reviews.models.ReviewRequest):
                The review request that the change is for.

            changedesc (reviewboard.changedescs.models.ChangeDescription):
                The change description for this entry.

            collapsed (bool):
                Whether the entry is collapsed by default.

            data (ReviewRequestPageData):
                Pre-queried data for the review request page.
            """
        super(ChangeEntry, self).__init__(changedesc.timestamp, collapsed)

        self.changedesc = changedesc
        self.fields_changed_groups = []
        cur_field_changed_group = None

        # See if there was a review request status change.
        status_change = changedesc.fields_changed.get('status')

        if status_change:
            assert 'new' in status_change
            self.new_status = ReviewRequest.status_to_string(
                status_change['new'][0])
        else:
            self.new_status = None

        # Process the list of fields, in order by fieldset. These will be
        # put into groups composed of inline vs. full-width field values,
        # for render into the box.
        fieldsets = get_review_request_fieldsets(
            include_main=True,
            include_change_entries_only=True)

        for fieldset in fieldsets:
            for field_cls in fieldset.field_classes:
                field_id = field_cls.field_id

                if field_id not in changedesc.fields_changed:
                    continue

                inline = field_cls.change_entry_renders_inline

                if (not cur_field_changed_group or
                    cur_field_changed_group['inline'] != inline):
                    # Begin a new group of fields.
                    cur_field_changed_group = {
                        'inline': inline,
                        'fields': [],
                    }
                    self.fields_changed_groups.append(cur_field_changed_group)

                if issubclass(field_cls, ReviewRequestPageDataMixin):
                    field = field_cls(review_request, request=request,
                                      data=data)
                else:
                    field = field_cls(review_request, request=request)

                cur_field_changed_group['fields'] += \
                    field.get_change_entry_sections_html(
                        changedesc.fields_changed[field_id])
