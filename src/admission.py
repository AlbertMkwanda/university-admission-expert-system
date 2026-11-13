"""Source-attributed eligibility matching for selected Malawi university programmes."""

import json
import math
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "config" / "admission_policy.json"
CATALOGUE_PATH = ROOT / "config" / "program_catalog.json"
DISCLAIMER = (
    "This matcher applies published minimum requirements; it is not an admission decision. "
    "Selection, equivalency, intake availability, and document verification remain with each institution."
)
POSTGRAD_CONDITION_FIELDS = {
    "gpa_5",
    "degree_type",
    "degree_classification",
    "degree_relevant",
    "degree_recognized",
    "relevant_work_years",
    "post_qualification_work_years",
    "capstone_completed",
    "professional_qualification_accepted",
}
POSTGRAD_REQUEST_FIELDS = {
    "level",
    "gpa_5",
    "degree_type",
    "degree_classification",
    "degree_relevance_by_program",
    "degree_recognized",
    "relevant_work_years_by_program",
    "post_qualification_work_years",
    "capstone_completed",
    "professional_qualification_accepted",
}
DEGREE_TYPES = {"bachelor", "honours", "professional", "none"}
DEGREE_CLASSIFICATIONS = {
    "credit",
    "strong_pass",
    "first_class",
    "second_class",
    "third_class",
    "unknown",
}
DISCIPLINE_ALIASES = {
    "Medicine": "Medicine and Health",
    "Medicine and Health": "Medicine and Health",
    "IT": "Information Technology",
    "Information Technology": "Information Technology",
    "Commerce": "Commerce and Business",
    "Commerce and Business": "Commerce and Business",
    "Engineering": "Engineering and Built Environment",
    "Engineering and Built Environment": "Engineering and Built Environment",
}


def available_disciplines(policy: dict[str, Any]) -> list[str]:
    """Return the normalized discipline choices represented in the catalogue."""
    return sorted({program["discipline"] for program in policy["programs"]})


def _normalize_discipline(field: str) -> str:
    return DISCIPLINE_ALIASES.get(field, field)


def load_policy(path: Path = POLICY_PATH) -> dict[str, Any]:
    """Load the catalog and reject malformed policy data before serving requests."""
    with path.open(encoding="utf-8") as policy_file:
        policy = json.load(policy_file)
    if not isinstance(policy, dict):
        raise ValueError("Admission policy must be a JSON object.")

    msce = policy.get("msce")
    postgraduate = policy.get("postgraduate")
    programs = policy.get("programs")
    if not isinstance(msce, dict) or not isinstance(postgraduate, dict):
        raise ValueError("Policy must define MSCE and postgraduate settings.")
    if not isinstance(programs, list) or not programs:
        raise ValueError("Policy programs must be a non-empty list.")
    subjects = msce.get("subjects")
    if not isinstance(subjects, list) or not subjects or len(set(subjects)) != len(subjects):
        raise ValueError("MSCE subjects must be a non-empty list of unique names.")

    if path == POLICY_PATH:
        if not CATALOGUE_PATH.is_file():
            raise ValueError("Programme catalogue file is missing.")
        with CATALOGUE_PATH.open(encoding="utf-8") as catalogue_file:
            catalogue = json.load(catalogue_file)
        if not isinstance(catalogue, dict) or not isinstance(catalogue.get("programs"), list):
            raise ValueError("Programme catalogue must contain a programs list.")
        if not isinstance(catalogue.get("coverage_note"), str) or not catalogue["coverage_note"]:
            raise ValueError("Programme catalogue must explain its coverage.")
        additional_institutions = catalogue.get("additional_institutions", [])
        if not isinstance(additional_institutions, list):
            raise ValueError("Additional institution entries must be a list.")
        for institution in additional_institutions:
            if not isinstance(institution, dict) or not {
                "name", "catalogue_url", "status", "note"
            }.issubset(institution):
                raise ValueError("Each additional institution needs a source and status note.")
        policy["additional_institutions"] = additional_institutions
        policy["programs"].extend(catalogue["programs"])
        policy["catalogue_coverage_note"] = catalogue["coverage_note"]

    program_ids = set()
    for program in programs:
        if not isinstance(program, dict):
            raise ValueError("Each programme must be an object.")
        required_fields = {"id", "name", "institution", "level", "field", "source_url"}
        if not required_fields.issubset(program):
            raise ValueError("Each programme must have its identity, level, field, and source.")
        if not isinstance(program["field"], str) or not program["field"]:
            raise ValueError(f"Programme {program['id']} needs a field.")
        program["discipline"] = _normalize_discipline(program["field"])
        if program["level"] not in {"undergraduate", "postgraduate"}:
            raise ValueError(f"Unknown programme level in {program['id']}.")
        if program["id"] in program_ids:
            raise ValueError(f"Duplicate programme id: {program['id']}.")
        program_ids.add(program["id"])
        rules_status = program.get("rules_status", "published")
        if not isinstance(rules_status, str) or rules_status not in {"published", "unavailable"}:
            raise ValueError(f"Unknown rules_status in {program['id']}.")
        if rules_status == "unavailable":
            if not isinstance(program.get("catalogue_source_url"), str):
                raise ValueError(f"Catalogue-only programme {program['id']} needs a catalogue source.")
            if "requirements" in program or "paths" in program:
                raise ValueError(f"Catalogue-only programme {program['id']} cannot define eligibility rules.")
            continue
        if program["level"] == "undergraduate":
            requirements = program.get("requirements")
            if not isinstance(requirements, dict):
                raise ValueError(f"Undergraduate programme {program['id']} needs requirements.")
            if not isinstance(requirements.get("minimum_credits"), int):
                raise ValueError(f"Undergraduate programme {program['id']} needs minimum_credits.")
        elif program["level"] == "postgraduate":
            paths = program.get("paths")
            if not isinstance(paths, list) or not paths:
                raise ValueError(f"Postgraduate programme {program['id']} needs eligibility paths.")
            for path_data in paths:
                if not isinstance(path_data.get("conditions"), list) or not path_data["conditions"]:
                    raise ValueError(f"Each path in {program['id']} needs conditions.")
                for condition in path_data["conditions"]:
                    if condition.get("field") not in POSTGRAD_CONDITION_FIELDS:
                        raise ValueError(f"Unknown postgraduate field in {program['id']}.")
                    if condition.get("operator") not in {"equals", "in", "minimum"}:
                        raise ValueError(f"Unsupported operator in {program['id']}.")
        else:
            raise ValueError(f"Unknown programme level in {program['id']}.")
    return policy


def _validate_msce_candidate(candidate: dict[str, Any], policy: dict[str, Any]) -> None:
    required_fields = {"level", "msce_results", "results_complete"}
    if set(candidate) not in (required_fields, required_fields | {"discipline"}):
        raise ValueError("Undergraduate requests need level, msce_results, and results_complete.")
    _validate_discipline(candidate, policy)
    results = candidate["msce_results"]
    if not isinstance(results, dict):
        raise ValueError("msce_results must map subject names to MSCE grades.")
    if len(results) > len(policy["msce"]["subjects"]):
        raise ValueError("Too many MSCE subject results were supplied.")
    for subject, grade in results.items():
        if subject not in policy["msce"]["subjects"]:
            raise ValueError(f"Unknown MSCE subject: {subject}.")
        if isinstance(grade, bool) or not isinstance(grade, int):
            raise ValueError(f"MSCE grade for {subject} must be a whole number from 1 to 9.")
        if not policy["msce"]["minimum_grade"] <= grade <= policy["msce"]["maximum_grade"]:
            raise ValueError(f"MSCE grade for {subject} must be a whole number from 1 to 9.")
    if not isinstance(candidate["results_complete"], bool):
        raise ValueError("results_complete must be true or false.")


def _validate_postgraduate_candidate(candidate: dict[str, Any], policy: dict[str, Any]) -> None:
    if set(candidate) not in (POSTGRAD_REQUEST_FIELDS, POSTGRAD_REQUEST_FIELDS | {"discipline"}):
        raise ValueError("Postgraduate requests must include all profile fields.")
    _validate_discipline(candidate, policy)
    gpa = candidate["gpa_5"]
    if (
        isinstance(gpa, bool)
        or not isinstance(gpa, (int, float))
        or not math.isfinite(gpa)
        or not policy["postgraduate"]["gpa_minimum"] <= gpa <= policy["postgraduate"]["gpa_maximum"]
    ):
        raise ValueError("gpa_5 must be a number from 0 to 5.")
    if not isinstance(candidate["degree_type"], str) or candidate["degree_type"] not in DEGREE_TYPES:
        raise ValueError("degree_type must be bachelor, honours, professional, or none.")
    if (
        not isinstance(candidate["degree_classification"], str)
        or candidate["degree_classification"] not in DEGREE_CLASSIFICATIONS
    ):
        raise ValueError("Select a supported degree classification or unknown.")
    for field in (
        "degree_recognized",
        "capstone_completed",
        "professional_qualification_accepted",
    ):
        if candidate[field] is not None and not isinstance(candidate[field], bool):
            raise ValueError(f"{field} must be true, false, or null.")

    degree_relevance_programs = {
        program["id"]
        for program in policy["programs"]
        if program["level"] == "postgraduate"
        and program.get("rules_status", "published") == "published"
        and any(
            condition["field"] == "degree_relevant"
            for path_data in program.get("paths", [])
            for condition in path_data["conditions"]
        )
    }
    relevance = candidate["degree_relevance_by_program"]
    if not isinstance(relevance, dict) or set(relevance) != degree_relevance_programs:
        raise ValueError("Provide a degree relevance answer for each programme that requires one.")
    if any(value is not None and not isinstance(value, bool) for value in relevance.values()):
        raise ValueError("Programme degree relevance must be true, false, or null.")

    experience_programs = {
        program["id"]
        for program in policy["programs"]
        if program["level"] == "postgraduate"
        and program.get("rules_status", "published") == "published"
        and any(
            condition["field"] == "relevant_work_years"
            for path_data in program.get("paths", [])
            for condition in path_data["conditions"]
        )
    }
    experience = candidate["relevant_work_years_by_program"]
    if not isinstance(experience, dict) or set(experience) != experience_programs:
        raise ValueError("Provide relevant work experience for each programme that requires it.")
    for value in experience.values():
        if value is not None and (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or not 0 <= value <= 60
        ):
            raise ValueError("Programme work experience must be a number from 0 to 60 or null.")

    value = candidate["post_qualification_work_years"]
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or not 0 <= value <= 60
    ):
        raise ValueError("post_qualification_work_years must be a number from 0 to 60.")


def _validate_discipline(candidate: dict[str, Any], policy: dict[str, Any]) -> None:
    if "discipline" in candidate and (
        not isinstance(candidate["discipline"], str)
        or candidate["discipline"] not in available_disciplines(policy)
    ):
        raise ValueError("Select a discipline represented in the programme catalogue.")


def _missing_result(value: bool | None, complete: bool) -> bool | None:
    return False if complete and value is None else value


def _check(required: str, passed: bool | None, message: str) -> dict[str, Any]:
    return {"rule": required, "passed": passed, "message": message}


def _evaluate_undergraduate(program: dict[str, Any], candidate: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    results = candidate["msce_results"]
    complete = candidate["results_complete"]
    requirements = program["requirements"]
    credit_maximum = policy["msce"]["credit_grade_maximum"]
    credits = sum(grade <= credit_maximum for grade in results.values())
    checks = [
        _check(
            "minimum_credits",
            credits >= requirements["minimum_credits"] if complete or credits >= requirements["minimum_credits"] else None,
            f"{credits} credit(s) entered; {requirements['minimum_credits']} required "
            f"(MSCE grades {credit_maximum} or better count as credits).",
        )
    ]

    for subject in requirements.get("required_credit_subjects", []):
        grade = results.get(subject)
        passed = _missing_result(None if grade is None else grade <= credit_maximum, complete)
        checks.append(
            _check(
                f"required_credit:{subject}",
                passed,
                f"{subject}: requires a credit (grade {credit_maximum} or better); "
                f"recorded {grade if grade is not None else 'not entered'}.",
            )
        )

    for subject, maximum in requirements.get("required_subject_grade_maximum", {}).items():
        grade = results.get(subject)
        passed = _missing_result(None if grade is None else grade <= maximum, complete)
        checks.append(
            _check(
                f"subject_grade:{subject}",
                passed,
                f"{subject}: requires grade {maximum} or better; "
                f"recorded {grade if grade is not None else 'not entered'}.",
            )
        )

    alternatives = requirements.get("one_of_credit_subject_groups", [])
    if alternatives:
        group_results = []
        maximum = requirements.get("one_of_subject_grade_maximum", credit_maximum)
        for group in alternatives:
            grades = [results.get(subject) for subject in group]
            group_passed = all(
                grade is not None and grade <= maximum for grade in grades
            )
            group_missing = any(grade is None for grade in grades)
            if group_passed:
                group_results.append(True)
            elif group_missing and not complete:
                group_results.append(None)
            else:
                group_results.append(False)
        passed = True if True in group_results else None if None in group_results else False
        choices = " or ".join(" + ".join(group) for group in alternatives)
        checks.append(
            _check(
                "one_of_credit_subject_groups",
                passed,
                f"At least one listed subject combination needs grades {maximum} or better: {choices}.",
            )
        )

    failed = any(check["passed"] is False for check in checks)
    pending = any(check["passed"] is None for check in checks)
    decision = "not_eligible" if failed else "needs_information" if pending else "eligible"
    return {
        **_program_summary(program),
        "decision": decision,
        "eligible": decision == "eligible",
        "credit_count": credits,
        "checks": checks,
    }


def _evaluate_condition(condition: dict[str, Any], candidate: dict[str, Any]) -> bool | None:
    actual = candidate[condition["field"]]
    if actual is None or (condition["field"] == "degree_classification" and actual == "unknown"):
        return None
    expected = condition["value"]
    operator = condition["operator"]
    if operator == "equals":
        return actual == expected
    if operator == "in":
        return actual in expected
    return actual >= expected


def _evaluate_postgraduate(program: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    profile = {
        **candidate,
        "degree_relevant": candidate["degree_relevance_by_program"][program["id"]]
        if program["id"] in candidate["degree_relevance_by_program"]
        else None,
        "relevant_work_years": candidate["relevant_work_years_by_program"][program["id"]]
        if program["id"] in candidate["relevant_work_years_by_program"]
        else None,
    }
    paths = []
    for path in program["paths"]:
        checks = [
            _check(
                condition["field"],
                _evaluate_condition(condition, profile),
                condition["label"],
            )
            for condition in path["conditions"]
        ]
        failed = any(check["passed"] is False for check in checks)
        pending = any(check["passed"] is None for check in checks)
        path_decision = "not_eligible" if failed else "needs_information" if pending else "eligible"
        paths.append({"path": path["label"], "decision": path_decision, "checks": checks})

    decision = (
        "eligible"
        if any(path["decision"] == "eligible" for path in paths)
        else "needs_information"
        if any(path["decision"] == "needs_information" for path in paths)
        else "not_eligible"
    )
    return {
        **_program_summary(program),
        "decision": decision,
        "eligible": decision == "eligible",
        "paths": paths,
    }


def _program_summary(program: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": program["id"],
        "name": program["name"],
        "institution": program["institution"],
        "field": program["field"],
        "discipline": program["discipline"],
        "school": program.get("school"),
        "intake": program.get("intake", "Not stated"),
        "source_url": program["source_url"],
        "catalogue_source_url": program.get("catalogue_source_url"),
        "rules_status": program.get("rules_status", "published"),
        "intake_source_url": program.get("intake_source_url"),
        "advisory": program.get("advisory", []),
    }


def _evaluate_catalogue_only(program: dict[str, Any]) -> dict[str, Any]:
    return {
        **_program_summary(program),
        "decision": "needs_information",
        "eligible": False,
        "message": (
            "This programme is listed in the institution's catalogue, but published "
            "admission criteria are not available in this checker."
        ),
    }


def evaluate_admission(candidate: Any, policy: dict[str, Any] | None = None) -> dict[str, Any]:
    """Match a candidate profile against the published rules for each configured programme."""
    if policy is None:
        policy = load_policy()
    if not isinstance(candidate, dict):
        raise ValueError("Request must be a JSON object.")
    level = candidate.get("level")
    discipline = candidate.get("discipline")
    if level == "undergraduate":
        _validate_msce_candidate(candidate, policy)
        matches = [
            _evaluate_catalogue_only(program)
            if program.get("rules_status") == "unavailable"
            else _evaluate_undergraduate(program, candidate, policy)
            for program in policy["programs"]
            if program["level"] == level
            and (discipline is None or program["discipline"] == discipline)
        ]
    elif level == "postgraduate":
        _validate_postgraduate_candidate(candidate, policy)
        matches = [
            _evaluate_catalogue_only(program)
            if program.get("rules_status") == "unavailable"
            else _evaluate_postgraduate(program, candidate)
            for program in policy["programs"]
            if program["level"] == level
            and (discipline is None or program["discipline"] == discipline)
        ]
    else:
        raise ValueError("level must be undergraduate or postgraduate.")

    decision = (
        "eligible"
        if any(match["decision"] == "eligible" for match in matches)
        else "needs_information"
        if not matches or any(match["decision"] == "needs_information" for match in matches)
        else "not_eligible"
    )
    response = {
        "level": level,
        "decision": decision,
        "eligible": decision == "eligible",
        "programs": matches,
        "disclaimer": DISCLAIMER,
        "policy": policy["policy_name"],
        "policy_version": policy["version"],
        "intake_note": policy["intake_note"],
        "catalogue_coverage_note": policy.get("catalogue_coverage_note"),
    }
    if discipline is not None:
        response["discipline"] = discipline
    if level == "postgraduate":
        response["gpa_5"] = candidate["gpa_5"]
        response["gpa_note"] = policy["postgraduate"]["note"]
    return response
