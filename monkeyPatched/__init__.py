from aqt import gui_hooks
from aqt.reviewer import Reviewer, ReviewerBottomBar
from anki.cards import Card
from typing import Any, Callable, Tuple
from anki.sched import Scheduler 
from aqt.utils import showWarning
from aqt.utils import tr, TR

# Do this monkey patching as long as the hooks have not been added to the real code
def _updateRevIvl_MonkeyPatched(self, card: Card, ease: int) -> None:
    idealIvl = self._nextRevIvl(card, ease)
    newIvl = min(
        max(self._adjRevIvl(card, idealIvl), card.ivl + 1),
        self._revConf(card)["maxIvl"],
    )
    newIvl = CardReviewIntervalOverrider.override_review_interval(
        newIvl, self, card, ease, idealIvl
    )
    card.ivl = newIvl

Scheduler._updateRevIvl = _updateRevIvl_MonkeyPatched


def _answerButtons_MonkeyPatched(self) -> str:
    default = self._defaultEase()

    def but(i, label):
        if i == default:
            extra = "id=defease"
        else:
            extra = ""
        due = self._buttonTime(i)
        return """
<td align=center>%s<button %s title="%s" data-ease="%s" onclick='pycmd("ease%d");'>\
%s</button></td>""" % (
            due,
            extra,
            _("Shortcut key: %s") % i,
            i,
            i,
            label,
        )

    buf = "<center><table cellpading=0 cellspacing=0><tr>"
    answerButtonTuples = self._answerButtonList()
    for ease, label in answerButtonTuples:
        buttonHtml = but(ease, label)
        buttonHtml = renderEasyButton(
            buttonHtml, self, ease, default, label, len(answerButtonTuples)
        )
        buf += buttonHtml
    buf += "</tr></table>"
    script = """
<script>$(function () { $("#defease").focus(); });</script>"""
    return buf + script

Reviewer._answerButtons = _answerButtons_MonkeyPatched


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
                showWarning("Enter a whole number between {0} and {1}.".format(smallestDay, biggestDay))
                return (True, None)
        
        # _answerCard() will call _answerRevCard() which calls _rescheduleRev() which calls _updateRevIvl()
        # use overrideDays only once in the next call to _answerCard() 
        context.reviewer._answerCard(ease)

        return (True, None)

    @staticmethod
    def override_review_interval(nextIvl: int, scheduler: Scheduler, card: Card, ease: int, idealIvl: int) -> int:
        if CardReviewIntervalOverrider.overrideDays:
            try:
                return CardReviewIntervalOverrider.overrideDays
            finally:
                CardReviewIntervalOverrider.overrideDays = None
        else:
            return nextIvl


# Use static class method as hook
gui_hooks.webview_did_receive_js_message.append(CardReviewIntervalOverrider.on_webview_did_receive_js_message)


def renderEasyButton(buttonHtml: str, reviewer: Reviewer, ease: int, defaultEase: int, label: str, numAnswerButtons: int) -> str:
    if numAnswerButtons < 3 or ease != numAnswerButtons:
        return buttonHtml
    # ease is for the last button, i.e. the Easy button => render it with an input field as label
        
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

