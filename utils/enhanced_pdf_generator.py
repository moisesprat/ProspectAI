#!/usr/bin/env python3
"""
Enhanced PDF Generator - Creates professional investment reports with decision support tools
"""

import os
import sys
from typing import Dict, Any, List, Optional
from datetime import datetime
import json
import math

# Add parent directory to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

try:
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch, cm
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
    from reportlab.graphics.shapes import Drawing, String, Line, Rect, Circle, Polygon
    from reportlab.graphics.charts.linecharts import HorizontalLineChart
    from reportlab.graphics.charts.piecharts import Pie
    from reportlab.graphics.charts.barcharts import VerticalBarChart
    from reportlab.graphics.charts.legends import Legend
    from reportlab.graphics import renderPDF
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    print("⚠️  ReportLab not available. Install with: pip install reportlab")

class EnhancedInvestmentReportPDFGenerator:
    """Generates professional PDF investment reports with decision support tools"""
    
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
        self.page_width = A4[0]
        self.page_height = A4[1]
    
    def _setup_custom_styles(self):
        """Setup custom paragraph styles for the report"""
        # Title style
        self.title_style = ParagraphStyle(
            'CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=28,
            spaceAfter=30,
            alignment=TA_CENTER,
            textColor=colors.darkblue,
            fontName='Helvetica-Bold'
        )
        
        # Executive summary style
        self.executive_style = ParagraphStyle(
            'CustomExecutive',
            parent=self.styles['Heading1'],
            fontSize=20,
            spaceAfter=20,
            spaceBefore=20,
            alignment=TA_CENTER,
            textColor=colors.darkred,
            fontName='Helvetica-Bold'
        )
        
        # Section header style
        self.section_style = ParagraphStyle(
            'CustomSection',
            parent=self.styles['Heading2'],
            fontSize=18,
            spaceAfter=15,
            spaceBefore=25,
            textColor=colors.darkblue,
            leftIndent=20,
            fontName='Helvetica-Bold'
        )
        
        # Subsection style
        self.subsection_style = ParagraphStyle(
            'CustomSubsection',
            parent=self.styles['Heading3'],
            fontSize=14,
            spaceAfter=10,
            spaceBefore=15,
            textColor=colors.darkblue,
            leftIndent=30,
            fontName='Helvetica-Bold'
        )
        
        # Body text style
        self.body_style = ParagraphStyle(
            'CustomBody',
            parent=self.styles['Normal'],
            fontSize=11,
            spaceAfter=8,
            alignment=TA_JUSTIFY,
            leftIndent=20,
            rightIndent=20,
            fontName='Helvetica'
        )
        
        # Highlight style
        self.highlight_style = ParagraphStyle(
            'CustomHighlight',
            parent=self.styles['Normal'],
            fontSize=11,
            spaceAfter=8,
            alignment=TA_LEFT,
            leftIndent=20,
            textColor=colors.darkgreen,
            fontName='Helvetica-Bold'
        )
        
        # Metric style
        self.metric_style = ParagraphStyle(
            'CustomMetric',
            parent=self.styles['Normal'],
            fontSize=10,
            spaceAfter=6,
            alignment=TA_LEFT,
            leftIndent=40,
            fontName='Helvetica'
        )
    
    def generate_comprehensive_investment_report(self, investment_strategy_output: Dict[str, Any], 
                                              output_path: str = None) -> str:
        """
        Generate a comprehensive PDF investment report with decision support tools
        
        Args:
            investment_strategy_output: Output from Investment Strategy Agent
            output_path: Path to save the PDF (optional)
            
        Returns:
            Path to the generated PDF file
        """
        if not REPORTLAB_AVAILABLE:
            raise ImportError("ReportLab is required for PDF generation. Install with: pip install reportlab")
        
        # Generate default output path if not provided
        if not output_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            sector = investment_strategy_output.get('sector', 'Unknown')
            output_path = f"enhanced_investment_report_{sector}_{timestamp}.pdf"
        
        # Create the PDF document
        doc = SimpleDocTemplate(output_path, pagesize=A4, rightMargin=36, leftMargin=36, 
                              topMargin=36, bottomMargin=36)
        
        # Build the story (content)
        story = []
        
        # Add title page
        story.extend(self._create_enhanced_title_page(investment_strategy_output))
        story.append(PageBreak())
        
        # Add executive summary
        story.extend(self._create_executive_summary(investment_strategy_output))
        story.append(PageBreak())
        
        # Add decision support dashboard
        story.extend(self._create_decision_dashboard(investment_strategy_output))
        story.append(PageBreak())
        
        # Add detailed stock analysis
        story.extend(self._create_detailed_stock_analysis(investment_strategy_output))
        story.append(PageBreak())
        
        # Add decision trees
        story.extend(self._create_decision_trees(investment_strategy_output))
        story.append(PageBreak())
        
        # Add portfolio allocation charts
        story.extend(self._create_portfolio_charts(investment_strategy_output))
        story.append(PageBreak())
        
        # Add risk assessment matrix
        story.extend(self._create_risk_matrix(investment_strategy_output))
        story.append(PageBreak())
        
        # Add action plan
        story.extend(self._create_action_plan(investment_strategy_output))
        
        # Build the PDF
        doc.build(story)
        
        print(f"✅ Enhanced PDF report generated successfully: {output_path}")
        return output_path
    
    def _create_enhanced_title_page(self, data: Dict[str, Any]) -> List:
        """Create an enhanced title page"""
        story = []
        
        # Main title
        title = Paragraph("INVESTMENT STRATEGY REPORT", self.title_style)
        story.append(title)
        story.append(Spacer(1, 40))
        
        # Sector information
        sector = data.get('sector', 'Unknown Sector')
        sector_text = Paragraph(f"Sector: {sector}", self.executive_style)
        story.append(sector_text)
        story.append(Spacer(1, 30))
        
        # Report metadata
        report_date = data.get('report_date', datetime.now().strftime("%B %d, %Y"))
        date_text = Paragraph(f"Report Date: {report_date}", self.body_style)
        story.append(date_text)
        
        analysis_date = data.get('analysis_date', 'N/A')
        if analysis_date != 'N/A':
            analysis_text = Paragraph(f"Analysis Date: {analysis_date}", self.body_style)
            story.append(analysis_text)
        
        story.append(Spacer(1, 50))
        
        # Key metrics summary
        story.extend(self._create_title_page_metrics(data))
        
        story.append(Spacer(1, 40))
        
        # Disclaimer
        disclaimer = Paragraph(
            "This report is generated by AI agents for informational purposes only. "
            "It should not be considered as financial advice. Always consult with a "
            "qualified financial advisor before making investment decisions.",
            self.body_style
        )
        story.append(disclaimer)
        
        return story
    
    def _create_title_page_metrics(self, data: Dict[str, Any]) -> List:
        """Create key metrics for the title page"""
        story = []
        
        # Extract key metrics
        stock_analyses = data.get('stock_analyses', [])
        total_stocks = len(stock_analyses)
        
        if total_stocks > 0:
            # Calculate aggregate metrics
            avg_technical_score = 0
            avg_momentum_score = 0
            buy_recommendations = 0
            
            for stock in stock_analyses:
                technical_score = stock.get('technical_score', {})
                if technical_score.get('percentage'):
                    avg_technical_score += technical_score['percentage']
                
                momentum = stock.get('momentum_analysis', {})
                if momentum.get('momentum_score'):
                    avg_momentum_score += momentum['momentum_score']
                
                if technical_score.get('recommendation') == 'Buy':
                    buy_recommendations += 1
            
            if total_stocks > 0:
                avg_technical_score /= total_stocks
                avg_momentum_score /= total_stocks
            
            # Create metrics table
            metrics_data = [
                ['Key Metrics', 'Value'],
                ['Total Stocks Analyzed', str(total_stocks)],
                ['Average Technical Score', f"{avg_technical_score:.1f}%"],
                ['Average Momentum Score', f"{avg_momentum_score:.1f}/10"],
                ['Buy Recommendations', f"{buy_recommendations}/{total_stocks}"],
                ['Sector', data.get('sector', 'Unknown')]
            ]
            
            metrics_table = Table(metrics_data, colWidths=[2*inch, 2*inch])
            metrics_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            story.append(metrics_table)
        
        return story
    
    def _create_executive_summary(self, data: Dict[str, Any]) -> List:
        """Create an enhanced executive summary"""
        story = []
        
        # Section header
        header = Paragraph("EXECUTIVE SUMMARY", self.executive_style)
        story.append(header)
        story.append(Spacer(1, 20))
        
        # Overall assessment
        overall_assessment = data.get('overall_assessment', 'No overall assessment available.')
        assessment_text = Paragraph(overall_assessment, self.body_style)
        story.append(assessment_text)
        story.append(Spacer(1, 15))
        
        # Key highlights
        key_highlights = data.get('key_highlights', [])
        if key_highlights:
            story.append(Paragraph("🎯 KEY HIGHLIGHTS", self.subsection_style))
            for highlight in key_highlights:
                highlight_text = Paragraph(f"• {highlight}", self.highlight_style)
                story.append(highlight_text)
            story.append(Spacer(1, 15))
        
        # Portfolio allocation summary
        portfolio_summary = data.get('portfolio_allocation_summary', 'No portfolio allocation available.')
        story.append(Paragraph("📊 PORTFOLIO STRATEGY", self.subsection_style))
        portfolio_text = Paragraph(portfolio_summary, self.body_style)
        story.append(portfolio_text)
        story.append(Spacer(1, 15))
        
        # Risk summary
        overall_risk = data.get('overall_risk_level', 'Risk level not specified.')
        story.append(Paragraph("⚠️ RISK PROFILE", self.subsection_style))
        risk_text = Paragraph(f"Overall Risk Level: {overall_risk}", self.body_style)
        story.append(risk_text)
        
        return story
    
    def _create_decision_dashboard(self, data: Dict[str, Any]) -> List:
        """Create a decision support dashboard"""
        story = []
        
        # Section header
        header = Paragraph("DECISION SUPPORT DASHBOARD", self.section_style)
        story.append(header)
        story.append(Spacer(1, 15))
        
        # Create decision matrix
        story.extend(self._create_decision_matrix(data))
        story.append(Spacer(1, 20))
        
        # Create quick decision guide
        story.extend(self._create_quick_decision_guide(data))
        
        return story
    
    def _create_decision_matrix(self, data: Dict[str, Any]) -> List:
        """Create a decision matrix for stocks"""
        story = []
        
        story.append(Paragraph("📈 STOCK DECISION MATRIX", self.subsection_style))
        story.append(Spacer(1, 10))
        
        stock_analyses = data.get('stock_analyses', [])
        if stock_analyses:
            # Create decision matrix table
            matrix_data = [['Stock', 'Technical Score', 'Momentum', 'Risk Level', 'Decision']]
            
            for stock in stock_analyses:
                ticker = stock.get('ticker', 'Unknown')
                technical_score = stock.get('technical_score', {})
                momentum = stock.get('momentum_analysis', {})
                
                tech_score = f"{technical_score.get('percentage', 'N/A')}%"
                momentum_score = f"{momentum.get('momentum_score', 'N/A')}/10"
                risk_level = momentum.get('risk_level', 'N/A')
                
                # Determine decision based on scores
                decision = self._determine_decision(technical_score, momentum, risk_level)
                
                matrix_data.append([ticker, tech_score, momentum_score, risk_level, decision])
            
            # Create table
            matrix_table = Table(matrix_data, colWidths=[1*inch, 1.2*inch, 1*inch, 1*inch, 1.2*inch])
            matrix_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('FONTSIZE', (0, 1), (-1, -1), 9)
            ]))
            
            story.append(matrix_table)
        
        return story
    
    def _create_quick_decision_guide(self, data: Dict[str, Any]) -> List:
        """Create a quick decision guide"""
        story = []
        
        story.append(Paragraph("🚀 QUICK DECISION GUIDE", self.subsection_style))
        story.append(Spacer(1, 10))
        
        guide_text = """
        <b>Technical Score + Momentum = Investment Decision</b><br/><br/>
        
        <b>🟢 STRONG BUY:</b> Technical Score > 80% + Momentum > 8/10<br/>
        <b>🟡 BUY:</b> Technical Score > 60% + Momentum > 6/10<br/>
        <b>🟠 HOLD:</b> Technical Score 40-60% + Momentum 4-6/10<br/>
        <b>🔴 SELL:</b> Technical Score < 40% + Momentum < 4/10<br/><br/>
        
        <b>Risk Considerations:</b><br/>
        • Low Risk: Stable technical indicators, strong fundamentals<br/>
        • Medium Risk: Mixed signals, moderate volatility<br/>
        • High Risk: Conflicting indicators, high volatility
        """
        
        guide_para = Paragraph(guide_text, self.body_style)
        story.append(guide_para)
        
        return story
    
    def _create_detailed_stock_analysis(self, data: Dict[str, Any]) -> List:
        """Create detailed analysis for each stock"""
        story = []
        
        # Section header
        header = Paragraph("DETAILED STOCK ANALYSIS", self.section_style)
        story.append(header)
        story.append(Spacer(1, 15))
        
        # Stock-by-stock analysis
        stock_analyses = data.get('stock_analyses', [])
        if stock_analyses:
            for stock in stock_analyses:
                story.extend(self._create_enhanced_stock_analysis(stock))
                story.append(Spacer(1, 25))
        
        return story
    
    def _create_enhanced_stock_analysis(self, stock: Dict[str, Any]) -> List:
        """Create enhanced analysis for a single stock"""
        story = []
        
        ticker = stock.get('ticker', 'Unknown')
        ticker_header = Paragraph(f"📊 {ticker} - COMPREHENSIVE ANALYSIS", self.subsection_style)
        story.append(ticker_header)
        story.append(Spacer(1, 10))
        
        # Create stock analysis table
        analysis_data = []
        
        # Market sentiment
        market_data = stock.get('market_analyst_data', {})
        if market_data:
            analysis_data.extend([
                ['Market Sentiment', f"{market_data.get('mention_count', 'N/A')} mentions"],
                ['Sentiment Score', f"{market_data.get('average_sentiment', 'N/A')}"],
                ['Relevance Score', f"{market_data.get('relevance_score', 'N/A')}"]
            ])
        
        # Technical analysis
        technical_score = stock.get('technical_score', {})
        if technical_score:
            analysis_data.extend([
                ['Technical Score', f"{technical_score.get('percentage', 'N/A')}%"],
                ['Technical Grade', technical_score.get('grade', 'N/A')],
                ['Technical Recommendation', technical_score.get('recommendation', 'N/A')]
            ])
        
        # Momentum analysis
        momentum = stock.get('momentum_analysis', {})
        if momentum:
            analysis_data.extend([
                ['Momentum Score', f"{momentum.get('momentum_score', 'N/A')}/10"],
                ['Risk Level', momentum.get('risk_level', 'N/A')],
                ['Trend Strength', momentum.get('trend_strength', 'N/A')]
            ])
        
        # Investment recommendation
        investment_rec = stock.get('investment_recommendation', 'No recommendation available.')
        analysis_data.append(['Investment Recommendation', investment_rec])
        
        # Create table
        if analysis_data:
            analysis_table = Table(analysis_data, colWidths=[2*inch, 3*inch])
            analysis_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.lightblue),
                ('TEXTCOLOR', (0, 0), (0, -1), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey])
            ]))
            
            story.append(analysis_table)
        
        return story
    
    def _create_decision_trees(self, data: Dict[str, Any]) -> List:
        """Create decision trees for investment decisions"""
        story = []
        
        # Section header
        header = Paragraph("DECISION TREES", self.section_style)
        story.append(header)
        story.append(Spacer(1, 15))
        
        # Create decision tree for buy/sell decisions
        story.extend(self._create_buy_sell_decision_tree())
        story.append(Spacer(1, 20))
        
        # Create decision tree for position sizing
        story.extend(self._create_position_sizing_tree())
        
        return story
    
    def _create_buy_sell_decision_tree(self) -> List:
        """Create a buy/sell decision tree"""
        story = []
        
        story.append(Paragraph("🔄 BUY/SELL DECISION TREE", self.subsection_style))
        story.append(Spacer(1, 10))
        
        tree_text = """
        <b>Start: Analyze Stock</b><br/><br/>
        
        <b>1. Technical Score Check:</b><br/>
        • Score > 80% → Consider Strong Buy<br/>
        • Score 60-80% → Consider Buy<br/>
        • Score 40-60% → Consider Hold<br/>
        • Score < 40% → Consider Sell<br/><br/>
        
        <b>2. Momentum Validation:</b><br/>
        • Momentum > 7/10 → Confirm Buy Decision<br/>
        • Momentum 5-7/10 → Proceed with Caution<br/>
        • Momentum < 5/10 → Reconsider Decision<br/><br/>
        
        <b>3. Risk Assessment:</b><br/>
        • Low Risk → Proceed with Decision<br/>
        • Medium Risk → Reduce Position Size<br/>
        • High Risk → Wait for Better Entry<br/><br/>
        
        <b>4. Final Decision:</b><br/>
        • Strong Buy: High Score + High Momentum + Low Risk<br/>
        • Buy: Good Score + Good Momentum + Acceptable Risk<br/>
        • Hold: Mixed Signals or High Risk<br/>
        • Sell: Poor Score + Poor Momentum
        """
        
        tree_para = Paragraph(tree_text, self.body_style)
        story.append(tree_para)
        
        return story
    
    def _create_position_sizing_tree(self) -> List:
        """Create a position sizing decision tree"""
        story = []
        
        story.append(Paragraph("📏 POSITION SIZING DECISION TREE", self.subsection_style))
        story.append(Spacer(1, 10))
        
        sizing_text = """
        <b>Position Sizing Based on Confidence Level:</b><br/><br/>
        
        <b>High Confidence (Score > 80% + Momentum > 8/10):</b><br/>
        • Core Position: 5-10% of portfolio<br/>
        • Consider options for leverage<br/><br/>
        
        <b>Medium Confidence (Score 60-80% + Momentum 6-8/10):</b><br/>
        • Standard Position: 3-5% of portfolio<br/>
        • Regular monitoring required<br/><br/>
        
        <b>Low Confidence (Score < 60% or Momentum < 6/10):</b><br/>
        • Small Position: 1-3% of portfolio<br/>
        • Strict stop-loss orders<br/><br/>
        
        <b>Risk-Adjusted Sizing:</b><br/>
        • Low Risk: Full position size<br/>
        • Medium Risk: 75% of position size<br/>
        • High Risk: 50% of position size
        """
        
        sizing_para = Paragraph(sizing_text, self.body_style)
        story.append(sizing_para)
        
        return story
    
    def _create_portfolio_charts(self, data: Dict[str, Any]) -> List:
        """Create portfolio allocation charts"""
        story = []
        
        # Section header
        header = Paragraph("PORTFOLIO ALLOCATION CHARTS", self.section_style)
        story.append(header)
        story.append(Spacer(1, 15))
        
        # Create pie chart for allocation
        story.extend(self._create_allocation_pie_chart(data))
        story.append(Spacer(1, 20))
        
        # Create bar chart for risk distribution
        story.extend(self._create_risk_bar_chart(data))
        
        return story
    
    def _create_allocation_pie_chart(self, data: Dict[str, Any]) -> List:
        """Create a pie chart for portfolio allocation"""
        story = []
        
        story.append(Paragraph("🥧 RECOMMENDED ALLOCATION", self.subsection_style))
        story.append(Spacer(1, 10))
        
        # Create pie chart
        drawing = Drawing(400, 200)
        
        # Sample allocation data (you can customize this based on your agent output)
        pie = Pie()
        pie.x = 150
        pie.y = 65
        pie.width = 150
        pie.height = 150
        
        stock_analyses = data.get('stock_analyses', [])
        if stock_analyses:
            # Calculate allocation based on technical scores
            total_score = 0
            stock_weights = []
            stock_names = []
            
            for stock in stock_analyses:
                technical_score = stock.get('technical_score', {})
                score = technical_score.get('percentage', 50)
                total_score += score
                stock_weights.append(score)
                stock_names.append(stock.get('ticker', 'Unknown'))
            
            if total_score > 0:
                # Normalize weights
                pie.data = [w/total_score*100 for w in stock_weights]
                pie.labels = stock_names
                pie.slices.strokeWidth = 0.5
                
                # Add colors
                colors_list = [colors.blue, colors.green, colors.red, colors.orange, colors.purple]
                for i, slice in enumerate(pie.slices):
                    slice.fillColor = colors_list[i % len(colors_list)]
                
                drawing.add(pie)
                
                # Add legend
                legend = Legend()
                legend.x = 320
                legend.y = 100
                legend.alignment = 'right'
                legend.fontName = 'Helvetica'
                legend.fontSize = 8
                legend.colorNamePairs = [(colors_list[i % len(colors_list)], stock_names[i]) for i in range(len(stock_names))]
                drawing.add(legend)
        
        story.append(drawing)
        
        return story
    
    def _create_risk_bar_chart(self, data: Dict[str, Any]) -> List:
        """Create a bar chart for risk distribution"""
        story = []
        
        story.append(Paragraph("📊 RISK DISTRIBUTION", self.subsection_style))
        story.append(Spacer(1, 10))
        
        # Create bar chart
        drawing = Drawing(400, 200)
        
        stock_analyses = data.get('stock_analyses', [])
        if stock_analyses:
            # Extract risk levels
            risk_levels = ['Low', 'Medium', 'High']
            risk_counts = [0, 0, 0]
            
            for stock in stock_analyses:
                momentum = stock.get('momentum_analysis', {})
                risk_level = momentum.get('risk_level', 'Medium')
                if risk_level == 'Low':
                    risk_counts[0] += 1
                elif risk_level == 'High':
                    risk_counts[2] += 1
                else:
                    risk_counts[1] += 1
            
            # Create bar chart
            chart = VerticalBarChart()
            chart.x = 50
            chart.y = 50
            chart.height = 125
            chart.width = 300
            chart.data = [risk_counts]
            chart.categoryAxis.categoryNames = risk_levels
            chart.valueAxis.valueMin = 0
            chart.valueAxis.valueMax = max(risk_counts) + 1
            chart.valueAxis.valueStep = 1
            
            # Style the chart
            chart.bars[0].fillColor = colors.lightblue
            chart.bars[0].strokeColor = colors.blue
            chart.bars[0].strokeWidth = 2
            
            drawing.add(chart)
        
        story.append(drawing)
        
        return story
    
    def _create_risk_matrix(self, data: Dict[str, Any]) -> List:
        """Create a risk-reward matrix"""
        story = []
        
        # Section header
        header = Paragraph("RISK-REWARD MATRIX", self.section_style)
        story.append(header)
        story.append(Spacer(1, 15))
        
        story.append(Paragraph("⚖️ RISK-REWARD ASSESSMENT", self.subsection_style))
        story.append(Spacer(1, 10))
        
        # Create risk matrix table
        matrix_data = [
            ['Risk Level', 'Technical Score', 'Momentum Score', 'Recommended Action', 'Position Size'],
            ['Low', '> 80%', '> 8/10', 'Strong Buy', '5-10%'],
            ['Low', '60-80%', '6-8/10', 'Buy', '3-5%'],
            ['Medium', '> 80%', '6-8/10', 'Buy', '3-5%'],
            ['Medium', '60-80%', '4-6/10', 'Hold/Buy Small', '1-3%'],
            ['High', '> 80%', '< 6/10', 'Wait/Reduce', '1-2%'],
            ['High', '< 60%', 'Any', 'Avoid/Sell', '0%']
        ]
        
        matrix_table = Table(matrix_data, colWidths=[1*inch, 1.2*inch, 1.2*inch, 1.5*inch, 1*inch])
        matrix_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.lightgreen, colors.lightblue, colors.lightyellow, colors.lightcoral])
        ]))
        
        story.append(matrix_table)
        
        return story
    
    def _create_action_plan(self, data: Dict[str, Any]) -> List:
        """Create an action plan section"""
        story = []
        
        # Section header
        header = Paragraph("ACTION PLAN", self.section_style)
        story.append(header)
        story.append(Spacer(1, 15))
        
        # Overall recommendation
        overall_rec = data.get('overall_recommendation', 'No overall recommendation available.')
        story.append(Paragraph("🎯 OVERALL STRATEGY", self.subsection_style))
        overall_text = Paragraph(overall_rec, self.body_style)
        story.append(overall_text)
        story.append(Spacer(1, 15))
        
        # Action items
        action_items = data.get('action_items', [])
        if action_items:
            story.append(Paragraph("📋 IMMEDIATE ACTIONS", self.subsection_style))
            for i, item in enumerate(action_items, 1):
                item_text = Paragraph(f"{i}. {item}", self.highlight_style)
                story.append(item_text)
            story.append(Spacer(1, 15))
        
        # Portfolio adjustments
        portfolio_adjustments = data.get('portfolio_adjustments', 'No portfolio adjustments recommended.')
        story.append(Paragraph("🔄 PORTFOLIO ADJUSTMENTS", self.subsection_style))
        adjustments_text = Paragraph(portfolio_adjustments, self.body_style)
        story.append(adjustments_text)
        story.append(Spacer(1, 15))
        
        # Monitoring plan
        story.append(Paragraph("👀 MONITORING PLAN", self.subsection_style))
        monitoring_text = """
        <b>Weekly:</b> Monitor technical indicators and momentum scores<br/>
        <b>Monthly:</b> Review portfolio allocation and rebalance if needed<br/>
        <b>Quarterly:</b> Comprehensive review of all positions and strategy<br/>
        <b>Annually:</b> Full portfolio audit and strategy adjustment
        """
        monitoring_para = Paragraph(monitoring_text, self.body_style)
        story.append(monitoring_para)
        
        return story
    
    def _determine_decision(self, technical_score: Dict, momentum: Dict, risk_level: str) -> str:
        """Determine investment decision based on scores"""
        try:
            tech_score = technical_score.get('percentage', 0)
            momentum_score = momentum.get('momentum_score', 0)
            
            if tech_score >= 80 and momentum_score >= 8 and risk_level == 'Low':
                return 'STRONG BUY'
            elif tech_score >= 60 and momentum_score >= 6:
                return 'BUY'
            elif tech_score >= 40 and momentum_score >= 4:
                return 'HOLD'
            else:
                return 'SELL'
        except:
            return 'HOLD'
    
    def generate_simple_enhanced_report(self, investment_strategy_output: Dict[str, Any], 
                                      output_path: str = None) -> str:
        """
        Generate a simple enhanced report with key decision tools
        
        Args:
            investment_strategy_output: Output from Investment Strategy Agent
            output_path: Path to save the PDF (optional)
            
        Returns:
            Path to the generated PDF file
        """
        if not REPORTLAB_AVAILABLE:
            raise ImportError("ReportLab is required for PDF generation. Install with: pip install reportlab")
        
        # Generate default output path if not provided
        if not output_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            sector = investment_strategy_output.get('sector', 'Unknown')
            output_path = f"simple_enhanced_report_{sector}_{timestamp}.pdf"
        
        # Create the PDF document
        doc = SimpleDocTemplate(output_path, pagesize=A4, rightMargin=36, leftMargin=36, 
                              topMargin=36, bottomMargin=36)
        
        # Build the story (content)
        story = []
        
        # Title
        title = Paragraph("Enhanced Investment Strategy Report", self.title_style)
        story.append(title)
        story.append(Spacer(1, 20))
        
        # Executive summary
        story.extend(self._create_executive_summary(investment_strategy_output))
        story.append(PageBreak())
        
        # Decision dashboard
        story.extend(self._create_decision_dashboard(investment_strategy_output))
        story.append(PageBreak())
        
        # Action plan
        story.extend(self._create_action_plan(investment_strategy_output))
        
        # Build the PDF
        doc.build(story)
        
        print(f"✅ Simple enhanced PDF report generated: {output_path}")
        return output_path

# Convenience function for quick enhanced PDF generation
def generate_enhanced_investment_pdf(investment_strategy_output: Dict[str, Any], 
                                   output_path: str = None, 
                                   report_type: str = "comprehensive") -> str:
    """
    Quick function to generate enhanced investment report PDF
    
    Args:
        investment_strategy_output: Output from Investment Strategy Agent
        output_path: Path to save the PDF (optional)
        report_type: "comprehensive" or "simple"
        
    Returns:
        Path to the generated PDF file
    """
    generator = EnhancedInvestmentReportPDFGenerator()
    
    if report_type == "comprehensive":
        return generator.generate_comprehensive_investment_report(investment_strategy_output, output_path)
    else:
        return generator.generate_simple_enhanced_report(investment_strategy_output, output_path)
