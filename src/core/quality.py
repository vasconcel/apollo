class QualityEngine:
    def __init__(self, threshold=2.0):
        self.threshold = threshold

    def evaluate(self, scores_dict):
        total = sum(scores_dict.values())

        decision = "include" if total >= self.threshold else "exclude"

        return {
            "total_score": total,
            "decision": decision
        }

    def validate_dual_assessment(self, assessments):
        """
        assessments: lista de avaliações do mesmo artigo
        """

        if len(assessments) < 2:
            return "insufficient"

        decisions = [a["decision"] for a in assessments]

        if len(set(decisions)) == 1:
            return "consensus"
        else:
            return "conflict"