from app.main import app


def test_broker_route_surface_exposes_supported_submission_routes():
    broker_routes = {
        (method, route.path)
        for route in app.routes
        if hasattr(route, "methods") and route.path.startswith("/api/v1/broker")
        for method in route.methods
    }

    expected_routes = {
        ("POST", "/api/v1/broker/claims/ready"),
        ("POST", "/api/v1/broker/claims/entity"),
        ("POST", "/api/v1/broker/claims/batch"),
        ("POST", "/api/v1/broker/validation"),
        ("POST", "/api/v1/broker/reports/{attempt_id}"),
        ("POST", "/api/v1/broker/attempts/{attempt_id}/finalise"),
    }

    assert expected_routes.issubset(broker_routes)


def test_broker_route_surface_does_not_expose_removed_legacy_routes():
    broker_routes = {
        (method, route.path)
        for route in app.routes
        if hasattr(route, "methods") and route.path.startswith("/api/v1/broker")
        for method in route.methods
    }

    removed_routes = {
        ("POST", "/api/v1/broker/claim"),
        ("POST", "/api/v1/broker/organisms/{taxon_id}/claim"),
        ("POST", "/api/v1/broker/attempts/{attempt_id}/lease/renew"),
        ("POST", "/api/v1/broker/attempts/{attempt_id}/report"),
        ("GET", "/api/v1/broker/attempts"),
        ("GET", "/api/v1/broker/attempts/{attempt_id}"),
        ("GET", "/api/v1/broker/attempts/{attempt_id}/items"),
        ("GET", "/api/v1/broker/organisms/{taxon_id}/summary"),
    }

    assert broker_routes.isdisjoint(removed_routes)
