"""HTTP interface for the university admission expert system."""

from flask import Flask, jsonify, render_template, request
from werkzeug.exceptions import BadRequest

from src.admission import DISCLAIMER, available_disciplines, evaluate_admission, load_policy


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__, template_folder="../templates")
    app.config.from_mapping(JSON_SORT_KEYS=False)
    if test_config:
        app.config.update(test_config)
    policy = load_policy()

    @app.get("/")
    def home():
        postgraduate_profiles = []
        for program in policy["programs"]:
            if program["level"] != "postgraduate":
                continue
            condition_fields = {
                condition["field"]
                for path_data in program.get("paths", [])
                for condition in path_data["conditions"]
            }
            if "degree_relevant" in condition_fields or "relevant_work_years" in condition_fields:
                postgraduate_profiles.append(
                    {
                        **program,
                        "needs_degree_relevance": "degree_relevant" in condition_fields,
                        "needs_relevant_work": "relevant_work_years" in condition_fields,
                    }
                )
        return render_template(
            "index.html",
            policy=policy,
            disciplines=available_disciplines(policy),
            postgraduate_profiles=postgraduate_profiles,
            disclaimer=DISCLAIMER,
        )

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    @app.post("/api/admissions/evaluate")
    def evaluate():
        if not request.is_json:
            return jsonify({"error": "Content-Type must be application/json."}), 415
        try:
            candidate = request.get_json()
        except BadRequest:
            return jsonify({"error": "Request body must contain valid JSON."}), 400
        try:
            return jsonify(evaluate_admission(candidate, policy))
        except ValueError as error:
            return jsonify({"error": str(error)}), 400

    return app


app = create_app()
