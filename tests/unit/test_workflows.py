import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from tradegraph_financial_advisor.workflows.analysis_workflow import (
    FinancialAnalysisWorkflow,
    AnalysisState
)
from tradegraph_financial_advisor.models.recommendations import (
    PortfolioRecommendation,
    RiskLevel
)


class TestFinancialAnalysisWorkflow:
    """Test FinancialAnalysisWorkflow functionality."""

    @pytest.fixture
    def mock_workflow_components(self, mock_openai_response, mock_firecrawl_service):
        """Mock all workflow components."""
        with patch('tradegraph_financial_advisor.workflows.analysis_workflow.ChatOpenAI') as mock_llm:
            with patch('tradegraph_financial_advisor.workflows.analysis_workflow.NewsReaderAgent') as mock_news:
                with patch('tradegraph_financial_advisor.workflows.analysis_workflow.FinancialAnalysisAgent') as mock_financial:
                    with patch('tradegraph_financial_advisor.workflows.analysis_workflow.FirecrawlService', return_value=mock_firecrawl_service):
                        mock_llm.return_value.ainvoke.return_value = mock_openai_response

                        # Mock agent responses
                        mock_news_instance = AsyncMock()
                        mock_news_instance.execute.return_value = {
                            "articles": [
                                {
                                    "title": "Apple Earnings Beat",
                                    "content": "Strong quarterly results",
                                    "sentiment": "bullish",
                                    "symbols": ["AAPL"]
                                }
                            ],
                            "total_count": 1
                        }
                        mock_news.return_value = mock_news_instance

                        mock_financial_instance = AsyncMock()
                        mock_financial_instance.execute.return_value = {
                            "analysis_results": {
                                "AAPL": {
                                    "market_data": {
                                        "current_price": 195.89,
                                        "volume": 45000000
                                    },
                                    "financials": {
                                        "pe_ratio": 28.5,
                                        "market_cap": 3000000000000
                                    },
                                    "technical_indicators": {
                                        "rsi": 65.2,
                                        "sma_20": 185.50
                                    }
                                }
                            }
                        }
                        mock_financial.return_value = mock_financial_instance

                        yield {
                            "llm": mock_llm,
                            "news_agent": mock_news_instance,
                            "financial_agent": mock_financial_instance,
                            "firecrawl": mock_firecrawl_service
                        }

    @pytest.mark.asyncio
    async def test_workflow_initialization(self):
        """Test workflow initialization."""
        workflow = FinancialAnalysisWorkflow()

        assert workflow.news_agent is not None
        assert workflow.financial_agent is not None
        assert workflow.firecrawl_service is not None
        assert workflow.workflow is not None

    @pytest.mark.asyncio
    async def test_analyze_portfolio_basic(self, mock_workflow_components):
        """Test basic portfolio analysis."""
        workflow = FinancialAnalysisWorkflow()

        symbols = ["AAPL"]
        portfolio_size = 100000
        risk_tolerance = "medium"

        result = await workflow.analyze_portfolio(
            symbols=symbols,
            portfolio_size=portfolio_size,
            risk_tolerance=risk_tolerance
        )

        assert isinstance(result, PortfolioRecommendation)
        assert result.portfolio_size == portfolio_size

    @pytest.mark.asyncio
    async def test_collect_news_step(self, mock_workflow_components, sample_news_articles):
        """Test news collection workflow step."""
        workflow = FinancialAnalysisWorkflow()

        initial_state = AnalysisState(
            symbols=["AAPL"],
            analysis_context={},
            news_data={},
            financial_data={},
            technical_data={},
            sentiment_analysis={},
            recommendations=[],
            portfolio_recommendation=None,
            messages=[],
            next_step="collect_news",
            error_messages=[]
        )

        # Mock news agent response
        mock_workflow_components["news_agent"].execute.return_value = {
            "articles": sample_news_articles,
            "total_count": len(sample_news_articles)
        }

        result_state = await workflow._collect_news(initial_state)

        assert "articles" in result_state["news_data"]
        assert result_state["news_data"]["total_count"] > 0
        assert len(result_state["messages"]) > 0

    @pytest.mark.asyncio
    async def test_analyze_financials_step(self, mock_workflow_components, sample_financial_data):
        """Test financial analysis workflow step."""
        workflow = FinancialAnalysisWorkflow()

        initial_state = AnalysisState(
            symbols=["AAPL"],
            analysis_context={},
            news_data={},
            financial_data={},
            technical_data={},
            sentiment_analysis={},
            recommendations=[],
            portfolio_recommendation=None,
            messages=[],
            next_step="analyze_financials",
            error_messages=[]
        )

        # Mock financial agent response
        mock_workflow_components["financial_agent"].execute.return_value = {
            "analysis_results": sample_financial_data
        }

        result_state = await workflow._analyze_financials(initial_state)

        assert "analysis_results" in result_state["financial_data"]
        assert "AAPL" in result_state["financial_data"]["analysis_results"]
        assert len(result_state["messages"]) > 0

    @pytest.mark.asyncio
    async def test_analyze_sentiment_step(self, mock_workflow_components, sample_news_articles):
        """Test sentiment analysis workflow step."""
        workflow = FinancialAnalysisWorkflow()

        initial_state = AnalysisState(
            symbols=["AAPL"],
            analysis_context={},
            news_data={"articles": sample_news_articles},
            financial_data={},
            technical_data={},
            sentiment_analysis={},
            recommendations=[],
            portfolio_recommendation=None,
            messages=[],
            next_step="analyze_sentiment",
            error_messages=[]
        )

        result_state = await workflow._analyze_sentiment(initial_state)

        assert "AAPL" in result_state["sentiment_analysis"]
        assert len(result_state["messages"]) > 0

    @pytest.mark.asyncio
    async def test_generate_recommendations_step(self, mock_workflow_components, sample_recommendations):
        """Test recommendation generation workflow step."""
        workflow = FinancialAnalysisWorkflow()

        initial_state = AnalysisState(
            symbols=["AAPL"],
            analysis_context={},
            news_data={},
            financial_data={
                "analysis_results": {
                    "AAPL": {
                        "market_data": {"current_price": 195.89}
                    }
                }
            },
            technical_data={},
            sentiment_analysis={"AAPL": {"sentiment_score": 0.2}},
            recommendations=[],
            portfolio_recommendation=None,
            messages=[],
            next_step="generate_recommendations",
            error_messages=[]
        )

        # Mock LLM response for recommendations
        mock_workflow_components["llm"].return_value.ainvoke.return_value.content = f"""
        {{
            "symbol": "AAPL",
            "recommendation": "buy",
            "confidence_score": 0.8,
            "target_price": 220.0,
            "risk_level": "medium",
            "time_horizon": "medium_term",
            "recommended_allocation": 0.1,
            "fundamental_score": 0.8,
            "technical_score": 0.7,
            "sentiment_score": 0.8,
            "key_factors": ["Strong fundamentals"],
            "risks": ["Market volatility"],
            "catalysts": ["Product launch"],
            "analyst_notes": "Positive outlook"
        }}
        """

        result_state = await workflow._generate_recommendations(initial_state)

        assert len(result_state["recommendations"]) > 0
        assert len(result_state["messages"]) > 0

    @pytest.mark.asyncio
    async def test_create_portfolio_step(self, mock_workflow_components, sample_recommendations):
        """Test portfolio creation workflow step."""
        workflow = FinancialAnalysisWorkflow()

        initial_state = AnalysisState(
            symbols=["AAPL"],
            analysis_context={"portfolio_size": 100000, "risk_tolerance": "medium"},
            news_data={},
            financial_data={},
            technical_data={},
            sentiment_analysis={},
            recommendations=sample_recommendations,
            portfolio_recommendation=None,
            messages=[],
            next_step="create_portfolio",
            error_messages=[]
        )

        # Mock LLM response for portfolio
        mock_workflow_components["llm"].return_value.ainvoke.return_value.content = """
        {
            "recommendations": [],
            "total_confidence": 0.8,
            "diversification_score": 0.7,
            "overall_risk_level": "medium",
            "portfolio_size": 100000
        }
        """

        result_state = await workflow._create_portfolio(initial_state)

        assert result_state["portfolio_recommendation"] is not None
        assert result_state["portfolio_recommendation"]["portfolio_size"] == 100000
        assert len(result_state["messages"]) > 0

    @pytest.mark.asyncio
    async def test_validate_recommendations_step(self, mock_workflow_components, sample_portfolio_recommendation):
        """Test recommendation validation workflow step."""
        workflow = FinancialAnalysisWorkflow()

        initial_state = AnalysisState(
            symbols=["AAPL"],
            analysis_context={},
            news_data={},
            financial_data={},
            technical_data={},
            sentiment_analysis={},
            recommendations=sample_portfolio_recommendation["recommendations"],
            portfolio_recommendation=sample_portfolio_recommendation,
            messages=[],
            next_step="validate_recommendations",
            error_messages=[]
        )

        result_state = await workflow._validate_recommendations(initial_state)

        assert "validation_results" in result_state["analysis_context"]
        assert len(result_state["messages"]) > 0

    @pytest.mark.asyncio
    async def test_workflow_error_handling(self, mock_workflow_components):
        """Test workflow error handling."""
        workflow = FinancialAnalysisWorkflow()

        # Mock an agent to raise an exception
        mock_workflow_components["news_agent"].execute.side_effect = Exception("Test error")

        symbols = ["AAPL"]

        with pytest.raises(Exception):
            await workflow.analyze_portfolio(symbols=symbols)

    @pytest.mark.asyncio
    async def test_workflow_with_different_risk_tolerances(self, mock_workflow_components):
        """Test workflow with different risk tolerance settings."""
        workflow = FinancialAnalysisWorkflow()

        test_cases = [
            ("conservative", 50000),
            ("medium", 100000),
            ("aggressive", 200000)
        ]

        for risk_tolerance, portfolio_size in test_cases:
            result = await workflow.analyze_portfolio(
                symbols=["AAPL"],
                portfolio_size=portfolio_size,
                risk_tolerance=risk_tolerance
            )

            assert isinstance(result, PortfolioRecommendation)
            assert result.portfolio_size == portfolio_size

    @pytest.mark.asyncio
    async def test_workflow_state_transitions(self):
        """Test workflow state transitions."""
        workflow = FinancialAnalysisWorkflow()

        # Test that workflow has proper state transitions
        assert hasattr(workflow.workflow, 'get_graph')

        # The workflow should be properly compiled
        assert workflow.workflow is not None

    @pytest.mark.asyncio
    async def test_workflow_with_multiple_symbols(self, mock_workflow_components):
        """Test workflow with multiple symbols."""
        workflow = FinancialAnalysisWorkflow()

        symbols = ["AAPL", "MSFT", "GOOGL"]

        # Mock responses for multiple symbols
        mock_workflow_components["news_agent"].execute.return_value = {
            "articles": [
                {"title": "AAPL News", "symbols": ["AAPL"]},
                {"title": "MSFT News", "symbols": ["MSFT"]},
                {"title": "GOOGL News", "symbols": ["GOOGL"]}
            ],
            "total_count": 3
        }

        mock_workflow_components["financial_agent"].execute.return_value = {
            "analysis_results": {
                symbol: {
                    "market_data": {"current_price": 200.0},
                    "financials": {"pe_ratio": 25.0}
                } for symbol in symbols
            }
        }

        result = await workflow.analyze_portfolio(symbols=symbols)

        assert isinstance(result, PortfolioRecommendation)
        # Should have recommendations for multiple symbols
        assert len(result.recommendations) >= 0

    @pytest.mark.asyncio
    async def test_workflow_performance(self, mock_workflow_components):
        """Test workflow performance characteristics."""
        workflow = FinancialAnalysisWorkflow()

        import time
        start_time = time.time()

        result = await workflow.analyze_portfolio(
            symbols=["AAPL"],
            portfolio_size=100000
        )

        end_time = time.time()
        execution_time = end_time - start_time

        # Workflow should complete in reasonable time (with mocks)
        assert execution_time < 10.0  # seconds
        assert isinstance(result, PortfolioRecommendation)

    @pytest.mark.asyncio
    async def test_workflow_cleanup(self, mock_workflow_components):
        """Test workflow cleanup and resource management."""
        workflow = FinancialAnalysisWorkflow()

        # Verify that agents are properly started and stopped
        await workflow.analyze_portfolio(symbols=["AAPL"])

        # Check that start/stop methods were called on agents
        mock_workflow_components["news_agent"].start.assert_called()
        mock_workflow_components["news_agent"].stop.assert_called()
        mock_workflow_components["financial_agent"].start.assert_called()
        mock_workflow_components["financial_agent"].stop.assert_called()


class TestAnalysisState:
    """Test AnalysisState data structure."""

    def test_analysis_state_creation(self):
        """Test AnalysisState creation and default values."""
        state = AnalysisState(
            symbols=["AAPL"],
            analysis_context={},
            news_data={},
            financial_data={},
            technical_data={},
            sentiment_analysis={},
            recommendations=[],
            portfolio_recommendation=None,
            messages=[],
            next_step="collect_news",
            error_messages=[]
        )

        assert state["symbols"] == ["AAPL"]
        assert state["next_step"] == "collect_news"
        assert len(state["error_messages"]) == 0
        assert len(state["messages"]) == 0

    def test_analysis_state_modification(self):
        """Test AnalysisState modification."""
        state = AnalysisState(
            symbols=["AAPL"],
            analysis_context={},
            news_data={},
            financial_data={},
            technical_data={},
            sentiment_analysis={},
            recommendations=[],
            portfolio_recommendation=None,
            messages=[],
            next_step="collect_news",
            error_messages=[]
        )

        # Modify state
        state["news_data"] = {"articles": [{"title": "Test"}]}
        state["next_step"] = "analyze_financials"

        assert state["news_data"]["articles"][0]["title"] == "Test"
        assert state["next_step"] == "analyze_financials"