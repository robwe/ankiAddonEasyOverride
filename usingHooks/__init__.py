from typing import Any, Callable, Tuple
from aqt import gui_hooks
from anki import hooks
from aqt.reviewer import Reviewer, ReviewerBottomBar
from anki.cards import Card
from anki.sched import Scheduler 
from aqt.utils import showWarning
from aqt.utils import tr, TR


class CardReviewIntervalOverrider:
    overrideDays = None

    @staticmethod
    def on_webview_did_receive_js_message(handled: Tuple[bool, Any], message: str, context: Any) -> Tuple[bool, Any]:
        if not (isinstance(context, ReviewerBottomBar) and message.startswith("ease_")):
            return handled

        CardReviewIntervalOverrider.overrideDays = None
        ease = int(message[5:6])
        try:
            CardReviewIntervalOverrider.overrideDays = int(message[7:])
        finally:
            smallestDay = 1
            biggestDay = 36500
            if (CardReviewIntervalOverrider.overrideDays is None
                    or CardReviewIntervalOverrider.overrideDays < smallestDay
                    or CardReviewIntervalOverrider.overrideDays > biggestDay):
                showWarning(tr(TR.ERRORS_INVALID_INTEGER, start=smallestDay, end=biggestDay))
                return (True, None)
        
        # _answerCard() will call _answerRevCard() which calls _rescheduleRev() which calls _updateRevIvl()
        # use the hook in _updateRevIvl() only once in the next call to _answerCard() 
        hooks.scheduler_will_update_review_interval.append(CardReviewIntervalOverrider.override_review_interval)
        try:
            context.reviewer._answerCard(ease)
        finally:
            hooks.scheduler_will_update_review_interval.remove(CardReviewIntervalOverrider.override_review_interval)

        return (True, None)

    @staticmethod
    def override_review_interval(nextIvl: int, scheduler: Scheduler, card: Card, ease: int, idealIvl: int) -> int:
        try:
            return CardReviewIntervalOverrider.overrideDays
        finally:
            CardReviewIntervalOverrider.overrideDays = None # assert the override is done only once


# Use static class method as hook
gui_hooks.webview_did_receive_js_message.append(CardReviewIntervalOverrider.on_webview_did_receive_js_message)


def renderEasyButton(buttonHtml: str, reviewer: Reviewer, ease: int, defaultEase: int, label: str, numAnswerButtons: int) -> str:
    if numAnswerButtons < 3 or ease != numAnswerButtons:
        return buttonHtml
    # else: ease is for the last button, i.e. the Easy button => render it with an input field as label
        
    if ease == defaultEase:
        extra = "id=defease"
    else:
        extra = ""

    ivlSecs = reviewer.mw.col.sched.nextIvl(reviewer.card, ease)
    days = max(1, round(ivlSecs / 86400))
    dayStr = tr(TR.SCHEDULING_ANSWER_BUTTON_TIME_DAYS, amount="")
    # There seems to be a bug that the size attribute of the input tag is not respected.
    # Instead the max attribute is used to determine the width of the input field 
    # and further space is added for decimals.
    # As workaround the CSS max-width is set to reduce the width of the input field to
    # about 4 digits plus the space for the spinner.
    html = """
<td align=center>
<input type=number id=easyInput class=nobold value=%s min=1 max=36500 step=1 size=3 maxlength=5 style="max-width:44px; padding:0; margin-bottom:-3px">
<span class=nobold>%s</span><br>
<button %s title="%s" data-ease="%s" onclick='pycmd("ease_%d_" + document.getElementById("easyInput").value);'>%s</button>
</td>""" % (
        days,
        dayStr,
        extra,
        _("Shortcut key: %s") % ease,
        ease,
        ease,
        label,
    )
    return html

gui_hooks.reviewer_will_render_answer_button.append(renderEasyButton)