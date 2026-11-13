import unittest

from src.web import create_app


class AdmissionApiTests(unittest.TestCase):
    def setUp(self):
        self.client = create_app({"TESTING": True}).test_client()

    def test_home_and_health_are_available(self):
        home = self.client.get("/")
        self.assertEqual(home.status_code, 200)
        self.assertIn(b"Undergraduate", home.data)
        self.assertIn(b"Postgraduate", home.data)
        self.assertIn(b"grade 3 or better", home.data)
        self.assertIn(b"What do you want to study?", home.data)
        self.assertIn(b"University of Malawi", home.data)
        self.assertIn(b"https://dmisjbu.ac.mw/", home.data)
        self.assertNotIn(b"Search by programme", home.data)
        self.assertEqual(self.client.get("/health").json, {"status": "ok"})

    def test_evaluate_returns_source_attributed_undergraduate_matches(self):
        response = self.client.post(
            "/api/admissions/evaluate",
            json={
                "level": "undergraduate",
                "results_complete": True,
                "msce_results": {
                    "English": 6,
                    "Mathematics": 5,
                    "Biology": 5,
                    "Physical Science": 5,
                    "Geography": 6,
                    "History": 6,
                },
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json["eligible"])
        it_program = next(
            program
            for program in response.json["programs"]
            if program["id"] == "mubas-information-technology"
        )
        self.assertEqual(it_program["decision"], "eligible")
        self.assertTrue(it_program["source_url"].startswith("https://"))
        self.assertIn("not an admission decision", response.json["disclaimer"])
        catalogue_program = next(
            program
            for program in response.json["programs"]
            if program["id"] == "unima-catalog-bachelor-of-arts-human-resource-management"
        )
        self.assertEqual(catalogue_program["decision"], "needs_information")
        self.assertEqual(catalogue_program["rules_status"], "unavailable")

    def test_postgraduate_endpoint_includes_gpa_and_explicit_degree_rules(self):
        response = self.client.post(
            "/api/admissions/evaluate",
            json={
                "level": "postgraduate",
                "gpa_5": 3.75,
                "degree_type": "bachelor",
                "degree_classification": "strong_pass",
                "degree_relevance_by_program": {
                    "kuhes-master-public-health": True,
                    "mubas-mphil-information-technology": True,
                    "mubas-msc-electrical-engineering": True,
                },
                "degree_recognized": True,
                "relevant_work_years_by_program": {
                    "kuhes-master-public-health": 2,
                    "mubas-mphil-information-technology": 2,
                    "mubas-msc-electrical-engineering": 2,
                },
                "post_qualification_work_years": 2,
                "capstone_completed": True,
                "professional_qualification_accepted": False,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["gpa_5"], 3.75)
        mphil = next(
            program
            for program in response.json["programs"]
            if program["id"] == "mubas-mphil-information-technology"
        )
        self.assertEqual(mphil["decision"], "eligible")
        self.assertTrue(any(path["decision"] == "eligible" for path in mphil["paths"]))

    def test_api_filters_results_to_the_selected_discipline(self):
        response = self.client.post(
            "/api/admissions/evaluate",
            json={
                "level": "undergraduate",
                "discipline": "Information Technology",
                "results_complete": False,
                "msce_results": {"English": 6, "Mathematics": 5},
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["discipline"], "Information Technology")
        self.assertTrue(response.json["programs"])
        self.assertTrue(
            all(program["discipline"] == "Information Technology" for program in response.json["programs"])
        )

    def test_invalid_payload_and_content_type_have_explicit_errors(self):
        invalid = self.client.post(
            "/api/admissions/evaluate",
            json={"level": "undergraduate", "results_complete": True, "msce_results": {"English": 10}},
        )
        missing_type = self.client.post("/api/admissions/evaluate", data="{}")
        malformed = self.client.post(
            "/api/admissions/evaluate", data="{", content_type="application/json"
        )
        self.assertEqual(invalid.status_code, 400)
        self.assertIn("error", invalid.json)
        self.assertEqual(missing_type.status_code, 415)
        self.assertEqual(malformed.status_code, 400)
        self.assertIn("error", malformed.json)


if __name__ == "__main__":
    unittest.main()
