import unittest

from src.admission import evaluate_admission, load_policy


class AdmissionRuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = load_policy()

    def evaluate_program(self, result, program_id):
        return next(program for program in result["programs"] if program["id"] == program_id)

    def test_policy_contains_source_attributed_programmes_at_both_levels(self):
        programs = self.policy["programs"]
        self.assertTrue(any(program["level"] == "undergraduate" for program in programs))
        self.assertTrue(any(program["level"] == "postgraduate" for program in programs))
        self.assertTrue(all(program.get("source_url") for program in programs))
        self.assertEqual(self.policy["postgraduate"]["gpa_maximum"], 5.0)

    def test_catalogue_only_programmes_are_not_given_invented_eligibility_decisions(self):
        catalogue_programs = [
            program for program in self.policy["programs"]
            if program.get("rules_status") == "unavailable"
        ]
        self.assertGreaterEqual(len(catalogue_programs), 300)
        self.assertTrue(all(program.get("catalogue_source_url") for program in catalogue_programs))

        result = evaluate_admission(
            {
                "level": "undergraduate",
                "results_complete": True,
                "msce_results": {"English": 6, "Mathematics": 5, "Biology": 5},
            },
            self.policy,
        )
        unima_program = next(
            program for program in result["programs"]
            if program["id"] == "unima-catalog-bachelor-of-arts-human-resource-management"
        )
        self.assertEqual(unima_program["decision"], "needs_information")
        self.assertEqual(unima_program["rules_status"], "unavailable")
        self.assertIn("criteria are not available", unima_program["message"])
        self.assertNotIn("credit_count", unima_program)

    def test_selected_discipline_limits_recommendations_and_eligibility_results(self):
        result = evaluate_admission(
            {
                "level": "undergraduate",
                "discipline": "Information Technology",
                "results_complete": False,
                "msce_results": {"English": 6, "Mathematics": 5},
            },
            self.policy,
        )
        self.assertEqual(result["discipline"], "Information Technology")
        self.assertTrue(result["programs"])
        self.assertTrue(
            all(program["discipline"] == "Information Technology" for program in result["programs"])
        )
        self.assertTrue(
            any(program["id"] == "mubas-information-technology" for program in result["programs"])
        )

        invalid = {
            "level": "undergraduate",
            "discipline": "Unknown faculty",
            "results_complete": False,
            "msce_results": {},
        }
        with self.assertRaisesRegex(ValueError, "Select a discipline"):
            evaluate_admission(invalid, self.policy)

    def test_msce_credit_boundary_and_programme_specific_cutoff(self):
        result = evaluate_admission(
            {
                "level": "undergraduate",
                "results_complete": True,
                "msce_results": {
                    "English": 6,
                    "Mathematics": 4,
                    "Biology": 4,
                    "Physics": 4,
                    "Chemistry": 4,
                    "Geography": 6,
                    "History": 7,
                },
            },
            self.policy,
        )
        microbiology = self.evaluate_program(result, "must-medical-microbiology")
        mbbs = self.evaluate_program(result, "kuhes-mbbs")
        self.assertEqual(microbiology["decision"], "eligible")
        self.assertEqual(microbiology["credit_count"], 6)
        self.assertEqual(mbbs["decision"], "not_eligible")
        self.assertTrue(any(check["passed"] is False for check in mbbs["checks"]))

    def test_msce_best_score_boundary_for_mbbs_and_alternative_science(self):
        result = evaluate_admission(
            {
                "level": "undergraduate",
                "results_complete": True,
                "msce_results": {
                    "English": 6,
                    "Mathematics": 3,
                    "Biology": 3,
                    "Physics": 3,
                    "General Science": 3,
                    "Geography": 6,
                    "History": 6,
                },
            },
            self.policy,
        )
        self.assertEqual(self.evaluate_program(result, "kuhes-mbbs")["decision"], "eligible")

    def test_incomplete_msce_profile_is_not_misreported_as_ineligible(self):
        incomplete = evaluate_admission(
            {
                "level": "undergraduate",
                "results_complete": False,
                "msce_results": {"English": 6, "Biology": 5, "Physical Science": 5},
            },
            self.policy,
        )
        complete = evaluate_admission(
            {
                "level": "undergraduate",
                "results_complete": True,
                "msce_results": {"English": 6, "Biology": 5, "Physical Science": 5},
            },
            self.policy,
        )
        self.assertEqual(
            self.evaluate_program(incomplete, "mubas-information-technology")["decision"],
            "needs_information",
        )
        self.assertEqual(
            self.evaluate_program(complete, "mubas-information-technology")["decision"],
            "not_eligible",
        )

    def test_postgraduate_gpa_is_reported_but_not_used_as_a_hidden_cutoff(self):
        profile = {
            "level": "postgraduate",
            "gpa_5": 0.25,
            "degree_type": "bachelor",
            "degree_classification": "strong_pass",
            "degree_relevance_by_program": {
                "kuhes-master-public-health": False,
                "mubas-mphil-information-technology": False,
                "mubas-msc-electrical-engineering": False,
            },
            "degree_recognized": True,
            "relevant_work_years_by_program": {
                "kuhes-master-public-health": 0,
                "mubas-mphil-information-technology": 0,
                "mubas-msc-electrical-engineering": 0,
            },
            "post_qualification_work_years": 1,
            "capstone_completed": False,
            "professional_qualification_accepted": False,
        }
        low_gpa = evaluate_admission(profile, self.policy)
        profile["gpa_5"] = 4.95
        high_gpa = evaluate_admission(profile, self.policy)
        mba_low = self.evaluate_program(low_gpa, "mubas-mba")
        mba_high = self.evaluate_program(high_gpa, "mubas-mba")
        self.assertEqual(mba_low["decision"], "eligible")
        self.assertEqual(mba_low["decision"], mba_high["decision"])
        self.assertEqual(high_gpa["gpa_5"], 4.95)
        self.assertIn("do not publish a common conversion", high_gpa["gpa_note"])

    def test_mphil_alternative_path_uses_classification_and_experience(self):
        result = evaluate_admission(
            {
                "level": "postgraduate",
                "gpa_5": 3.8,
                "degree_type": "bachelor",
                "degree_classification": "strong_pass",
                "degree_relevance_by_program": {
                    "kuhes-master-public-health": False,
                    "mubas-mphil-information-technology": True,
                    "mubas-msc-electrical-engineering": False,
                },
                "degree_recognized": True,
                "relevant_work_years_by_program": {
                    "kuhes-master-public-health": 0,
                    "mubas-mphil-information-technology": 2,
                    "mubas-msc-electrical-engineering": 0,
                },
                "post_qualification_work_years": 2,
                "capstone_completed": False,
                "professional_qualification_accepted": False,
            },
            self.policy,
        )
        mphil = self.evaluate_program(result, "mubas-mphil-information-technology")
        self.assertEqual(mphil["decision"], "eligible")
        self.assertEqual(mphil["paths"][1]["decision"], "eligible")
        self.assertEqual(
            self.evaluate_program(result, "kuhes-master-public-health")["decision"],
            "not_eligible",
        )

    def test_unknown_degree_classification_requires_more_information(self):
        result = evaluate_admission(
            {
                "level": "postgraduate",
                "gpa_5": 3.2,
                "degree_type": "honours",
                "degree_classification": "unknown",
                "degree_relevance_by_program": {
                    "kuhes-master-public-health": True,
                    "mubas-mphil-information-technology": True,
                    "mubas-msc-electrical-engineering": True,
                },
                "degree_recognized": True,
                "relevant_work_years_by_program": {
                    "kuhes-master-public-health": 0,
                    "mubas-mphil-information-technology": 0,
                    "mubas-msc-electrical-engineering": 0,
                },
                "post_qualification_work_years": 0,
                "capstone_completed": False,
                "professional_qualification_accepted": False,
            },
            self.policy,
        )
        self.assertEqual(
            self.evaluate_program(result, "mubas-mphil-information-technology")["decision"],
            "needs_information",
        )

    def test_engineering_professional_route_requires_accreditation_and_equivalency(self):
        profile = {
            "level": "postgraduate",
            "gpa_5": 3.2,
            "degree_type": "professional",
            "degree_classification": "unknown",
            "degree_relevance_by_program": {
                "kuhes-master-public-health": False,
                "mubas-mphil-information-technology": False,
                "mubas-msc-electrical-engineering": True,
            },
            "degree_recognized": True,
            "relevant_work_years_by_program": {
                "kuhes-master-public-health": 0,
                "mubas-mphil-information-technology": 0,
                "mubas-msc-electrical-engineering": 0,
            },
            "post_qualification_work_years": 0,
            "capstone_completed": False,
            "professional_qualification_accepted": True,
        }
        accepted = evaluate_admission(profile, self.policy)
        engineering = self.evaluate_program(accepted, "mubas-msc-electrical-engineering")
        self.assertEqual(engineering["decision"], "eligible")
        profile["degree_recognized"] = False
        rejected = evaluate_admission(profile, self.policy)
        self.assertEqual(
            self.evaluate_program(rejected, "mubas-msc-electrical-engineering")["decision"],
            "not_eligible",
        )

    def test_rejects_invalid_grades_profiles_and_gpa(self):
        invalid_candidates = [
            {
                "level": "undergraduate",
                "results_complete": True,
                "msce_results": {"English": 0},
            },
            {
                "level": "undergraduate",
                "results_complete": True,
                "msce_results": {"English": 9.5},
            },
            {
                "level": "undergraduate",
                "results_complete": True,
                "msce_results": {"Unknown subject": 3},
            },
            {
                "level": "postgraduate",
                "gpa_5": 5.1,
                "degree_type": "bachelor",
                "degree_classification": "strong_pass",
                "degree_relevance_by_program": {
                    "kuhes-master-public-health": True,
                    "mubas-mphil-information-technology": True,
                    "mubas-msc-electrical-engineering": True,
                },
                "degree_recognized": True,
                "relevant_work_years_by_program": {
                    "kuhes-master-public-health": 0,
                    "mubas-mphil-information-technology": 0,
                    "mubas-msc-electrical-engineering": 0,
                },
                "post_qualification_work_years": 0,
                "capstone_completed": False,
                "professional_qualification_accepted": False,
            },
            {
                "level": "postgraduate",
                "gpa_5": 3.2,
                "degree_type": [],
                "degree_classification": "unknown",
                "degree_relevance_by_program": {
                    "kuhes-master-public-health": None,
                    "mubas-mphil-information-technology": None,
                    "mubas-msc-electrical-engineering": None,
                },
                "degree_recognized": None,
                "relevant_work_years_by_program": {
                    "kuhes-master-public-health": None,
                    "mubas-mphil-information-technology": None,
                    "mubas-msc-electrical-engineering": None,
                },
                "post_qualification_work_years": 0,
                "capstone_completed": None,
                "professional_qualification_accepted": None,
            },
        ]
        for candidate in invalid_candidates:
            with self.subTest(candidate=candidate), self.assertRaises(ValueError):
                evaluate_admission(candidate, self.policy)


if __name__ == "__main__":
    unittest.main()
