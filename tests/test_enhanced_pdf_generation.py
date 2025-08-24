#!/usr/bin/env python3
"""
Test Enhanced PDF Generation - Demonstrate creating professional investment reports with decision support tools
"""

import os
import sys
import json
from typing import Dict, Any

# Add parent directory to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from utils.enhanced_pdf_generator import generate_enhanced_investment_pdf, EnhancedInvestmentReportPDFGenerator

def test_enhanced_pdf_generation():
    """Test enhanced PDF generation with sample Investment Strategy Agent output"""
    
    print("📄 TESTING ENHANCED PDF GENERATION")
    print("=" * 60)
    print("This test demonstrates creating professional investment reports with:")
    print("• Executive Summary")
    print("• Decision Support Dashboard")
    print("• Decision Trees")
    print("• Portfolio Charts")
    print("• Risk-Reward Matrix")
    print("=" * 60)
    
    # Sample Investment Strategy Agent output (what you'll get from your final agent)
    sample_investment_output = {
        "sector": "Technology",
        "report_date": "August 24, 2025",
        "analysis_date": "2025-08-24 01:06:06",
        "overall_assessment": "The Technology sector presents exceptional investment opportunities with a strong bullish outlook driven by AI advancements, robust technical momentum, and positive social sentiment. The combination of strong fundamentals, technical indicators, and market sentiment suggests continued upward trajectory for leading tech stocks.",
        "key_highlights": [
            "Strong technical momentum across leading tech stocks with average scores of 6/10",
            "Reddit sentiment analysis shows bullish outlook for AI-focused companies",
            "Technical indicators suggest continued upward trend with low volatility",
            "Portfolio allocation should favor growth stocks with strong fundamentals",
            "Risk-adjusted returns favor overweighting Technology sector",
            "AI and cloud computing leaders show strongest momentum signals"
        ],
        "portfolio_allocation_summary": "Recommended allocation: 40% growth stocks (NVDA, META), 30% established tech (GOOGL, AAPL), 20% emerging tech, 10% defensive positions. Focus on companies with strong technical momentum and positive social sentiment. Consider options strategies for enhanced returns on high-conviction positions.",
        "stock_analyses": [
            {
                "ticker": "NVDA",
                "market_analyst_data": {
                    "mention_count": 10,
                    "average_sentiment": 0.589,
                    "relevance_score": 0.378,
                    "reddit_rationale": "Strong bullish sentiment driven by AI product launches and analyst upgrades"
                },
                "technical_score": {
                    "percentage": 71.43,
                    "grade": "B (Buy)",
                    "recommendation": "Buy"
                },
                "momentum_analysis": {
                    "momentum_score": 6,
                    "risk_level": "Low",
                    "trend_strength": "Strong",
                    "key_signals": ["Bullish momentum", "Support level identified"]
                },
                "investment_recommendation": "Strong buy recommendation for NVDA based on positive technical momentum, strong Reddit sentiment, and AI leadership position. Consider accumulating on pullbacks to support levels. Recommended position size: 5-8% of portfolio."
            },
            {
                "ticker": "META",
                "market_analyst_data": {
                    "mention_count": 17,
                    "average_sentiment": 0.32,
                    "relevance_score": 0.366,
                    "reddit_rationale": "Mixed sentiment due to regulatory concerns but strong technical setup"
                },
                "technical_score": {
                    "percentage": 71.43,
                    "grade": "B (Buy)",
                    "recommendation": "Buy"
                },
                "momentum_analysis": {
                    "momentum_score": 6,
                    "risk_level": "Low",
                    "trend_strength": "Strong",
                    "key_signals": ["Bullish momentum", "Resistance level identified"]
                },
                "investment_recommendation": "Cautious buy for META. Strong technical indicators offset regulatory concerns. Monitor regulatory developments and consider position sizing based on risk tolerance. Recommended position size: 3-5% of portfolio."
            },
            {
                "ticker": "GOOGL",
                "market_analyst_data": {
                    "mention_count": 3,
                    "average_sentiment": 0.719,
                    "relevance_score": 0.362,
                    "reddit_rationale": "Very positive sentiment around AI and cloud services"
                },
                "technical_score": {
                    "percentage": 85.0,
                    "grade": "A (Strong Buy)",
                    "recommendation": "Strong Buy"
                },
                "momentum_analysis": {
                    "momentum_score": 8,
                    "risk_level": "Low",
                    "trend_strength": "Very Strong",
                    "key_signals": ["Strong bullish momentum", "Breakout pattern"]
                },
                "investment_recommendation": "Strong buy for GOOGL with highest technical score and momentum. Excellent risk-reward profile with strong fundamentals. Recommended position size: 8-10% of portfolio."
            }
        ],
        "overall_recommendation": "The Technology sector warrants increased allocation with focus on AI and cloud computing leaders. Maintain diversified exposure while overweighting stocks with strong technical momentum and positive social sentiment. Consider using covered calls on existing positions to generate additional income.",
        "action_items": [
            "Increase Technology sector allocation to 25-30% of portfolio",
            "Initiate positions in GOOGL (8-10%), NVDA (5-8%), and META (3-5%)",
            "Set stop-loss orders at identified support levels",
            "Monitor regulatory developments for META and other social media stocks",
            "Consider options strategies for enhanced returns on high-conviction positions",
            "Rebalance portfolio monthly to maintain target allocations",
            "Implement dollar-cost averaging for new positions"
        ],
        "portfolio_adjustments": "Rebalance portfolio to overweight Technology sector. Reduce exposure to defensive sectors and increase growth allocation. Consider using covered calls on existing tech positions to generate additional income. Maintain 10% cash for opportunistic entries.",
        "overall_risk_level": "Medium",
        "risk_factors": [
            "Market volatility and potential tech sector corrections",
            "Regulatory risks for social media and AI companies",
            "Geopolitical tensions affecting semiconductor supply chains",
            "Interest rate sensitivity of growth stocks",
            "AI bubble concerns and valuation risks",
            "Earnings volatility in high-growth tech companies"
        ],
        "risk_mitigation_strategies": "Implement dollar-cost averaging for new positions, maintain stop-loss orders, diversify across subsectors, and consider hedging strategies. Regular portfolio rebalancing and position sizing based on risk tolerance. Use options for downside protection.",
        "analysis_methodology": "This analysis combines Reddit sentiment analysis, comprehensive technical indicators (13+ indicators), LLM-generated momentum analysis, and fundamental considerations. Data sources include Reddit API, Yahoo Finance, and proprietary technical analysis algorithms. Risk assessment incorporates multiple factors including volatility, correlation, and market conditions.",
        "data_sources": [
            "Reddit API for social sentiment analysis",
            "Yahoo Finance for stock price data and technical indicators",
            "Proprietary technical analysis algorithms",
            "LLM analysis for momentum and risk assessment",
            "Market analyst insights and Reddit community sentiment",
            "Real-time market data and news sentiment analysis"
        ]
    }
    
    print(f"\n📊 Sample Investment Strategy Output:")
    print(f"  - Sector: {sample_investment_output['sector']}")
    print(f"  - Stocks analyzed: {len(sample_investment_output['stock_analyses'])}")
    print(f"  - Overall risk level: {sample_investment_output['overall_risk_level']}")
    print(f"  - Action items: {len(sample_investment_output['action_items'])}")
    
    # Test Enhanced PDF generation
    print(f"\n{'='*20} TESTING ENHANCED PDF GENERATION {'='*20}")
    
    try:
        # Test 1: Comprehensive Enhanced PDF report
        print(f"🔧 Generating comprehensive enhanced PDF report...")
        comprehensive_pdf = generate_enhanced_investment_pdf(
            sample_investment_output, 
            report_type="comprehensive"
        )
        print(f"✅ Comprehensive enhanced PDF generated: {comprehensive_pdf}")
        
        # Test 2: Simple Enhanced PDF report
        print(f"🔧 Generating simple enhanced PDF report...")
        simple_pdf = generate_enhanced_investment_pdf(
            sample_investment_output, 
            report_type="simple"
        )
        print(f"✅ Simple enhanced PDF generated: {simple_pdf}")
        
        # Test 3: Custom Enhanced PDF with specific filename
        print(f"🔧 Generating custom enhanced PDF report...")
        custom_pdf = generate_enhanced_investment_pdf(
            sample_investment_output, 
            output_path="enhanced_tech_investment_report.pdf",
            report_type="comprehensive"
        )
        print(f"✅ Custom enhanced PDF generated: {custom_pdf}")
        
        # Show file information
        print(f"\n📁 GENERATED ENHANCED PDF FILES:")
        print("-" * 50)
        for pdf_file in [comprehensive_pdf, simple_pdf, custom_pdf]:
            if os.path.exists(pdf_file):
                file_size = os.path.getsize(pdf_file) / 1024  # KB
                print(f"  📄 {pdf_file}")
                print(f"     Size: {file_size:.1f} KB")
                print(f"     Path: {os.path.abspath(pdf_file)}")
                print()
        
        print("🎉 Enhanced PDF generation test completed successfully!")
        print("\n💡 Your enhanced PDF reports now include:")
        print("  ✅ Executive Summary with key insights")
        print("  ✅ Decision Support Dashboard with matrix")
        print("  ✅ Decision Trees for buy/sell decisions")
        print("  ✅ Portfolio Allocation Charts (pie charts)")
        print("  ✅ Risk Distribution Charts (bar charts)")
        print("  ✅ Risk-Reward Matrix for position sizing")
        print("  ✅ Action Plan with monitoring schedule")
        
    except Exception as e:
        print(f"❌ Error testing enhanced PDF generation: {str(e)}")
        import traceback
        traceback.print_exc()

def test_enhanced_pdf_generator_class():
    """Test the enhanced PDF generator class directly"""
    
    print(f"\n{'='*20} TESTING ENHANCED PDF GENERATOR CLASS {'='*20}")
    
    try:
        # Create generator instance
        generator = EnhancedInvestmentReportPDFGenerator()
        print("✅ Enhanced PDF generator instance created successfully")
        
        # Test custom styling
        print(f"✅ Enhanced styles configured:")
        print(f"  - Title style: {generator.title_style.fontSize}pt, {generator.title_style.textColor}")
        print(f"  - Executive style: {generator.executive_style.fontSize}pt, {generator.executive_style.textColor}")
        print(f"  - Section style: {generator.section_style.fontSize}pt, {generator.section_style.textColor}")
        print(f"  - Highlight style: {generator.highlight_style.fontSize}pt, {generator.highlight_style.textColor}")
        
        # Test decision determination
        test_tech_score = {"percentage": 85}
        test_momentum = {"momentum_score": 8}
        test_risk = "Low"
        
        decision = generator._determine_decision(test_tech_score, test_momentum, test_risk)
        print(f"✅ Decision logic test: Score 85% + Momentum 8/10 + Low Risk = {decision}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing enhanced PDF generator class: {str(e)}")
        return False

def show_enhanced_features():
    """Show the enhanced features available"""
    
    print(f"\n{'='*20} ENHANCED PDF FEATURES {'='*20}")
    
    features = [
        "🎯 Executive Summary - Key insights and portfolio strategy",
        "📊 Decision Support Dashboard - Stock decision matrix",
        "🚀 Quick Decision Guide - Color-coded decision rules",
        "🔄 Decision Trees - Buy/sell and position sizing logic",
        "🥧 Portfolio Charts - Pie charts for allocation",
        "📈 Risk Charts - Bar charts for risk distribution",
        "⚖️ Risk-Reward Matrix - Position sizing recommendations",
        "📋 Action Plan - Immediate actions and monitoring schedule",
        "👀 Monitoring Plan - Weekly/monthly/quarterly review schedule"
    ]
    
    for feature in features:
        print(f"  {feature}")
    
    print(f"\n💡 Integration with your Investment Strategy Agent:")
    print("  • Automatically generates professional reports")
    print("  • Includes all agent insights and recommendations")
    print("  • Provides decision support tools for investors")
    print("  • Creates shareable, professional PDFs")

if __name__ == "__main__":
    # Test enhanced PDF generator class
    if test_enhanced_pdf_generator_class():
        # Show enhanced features
        show_enhanced_features()
        # Test enhanced PDF generation
        test_enhanced_pdf_generation()
    else:
        print("❌ Enhanced PDF generator class test failed, skipping PDF generation test")
