"""
Create sample validation dataset for APOLLO testing
"""
import pandas as pd

# Create WL test data with specific scenarios
wl_data = [
    # Normal cases that should be INCLUDED (pass EC, pass IC, pass QC)
    {'Library': 'IEEE', 'Global_ID': 'W1', 'Local_ID': '1', 
     'Title': 'Software Engineering Hiring Practices in Tech Companies', 
     'Abstract': 'This study examines hiring practices in software engineering companies through a systematic survey of 500 organizations across multiple countries. We analyze recruitment channels, interview processes, and hiring criteria. Results show a strong preference for technical skills over soft skills in initial screening stages. The methodology includes statistical analysis of survey responses and comparative analysis of hiring outcomes. Limitations and threats to validity are discussed.',
     'Keywords': 'software engineering, hiring, recruitment'},
    
    {'Library': 'Scopus', 'Global_ID': 'W2', 'Local_ID': '2', 
     'Title': 'Agile Development Team Composition and Performance', 
     'Abstract': 'We investigate the relationship between team composition and project success in agile software development. Using data from 50 development teams across various organizations in the technology sector, we find that diverse teams outperform homogeneous ones in complex projects. The research methodology combines quantitative analysis of project metrics with qualitative interviews. Our findings have implications for team hiring practices.',
     'Keywords': 'agile, software development, team composition'},
    
    {'Library': 'Springer', 'Global_ID': 'W3', 'Local_ID': '3', 
     'Title': 'Developer Productivity in Remote Work Environments', 
     'Abstract': 'This paper presents a comprehensive study of developer productivity in remote work settings. Through a controlled experiment with 100 developers working remotely, we measure output metrics including code commits, pull request frequency, and sprint completion rates. The study identifies key factors affecting productivity such as communication tools, time zone differences, and work-life boundaries. Limitations include self-selection bias.',
     'Keywords': 'remote work, developer productivity, software engineering'},
    
    # Cases that fail EC1 (not SE research)
    {'Library': 'IEEE', 'Global_ID': 'W4', 'Local_ID': '4', 
     'Title': 'Climate Change Impact on Agricultural Yields', 
     'Abstract': 'This study examines the effects of climate change on agricultural productivity in developing nations. We use satellite imagery and statistical models to predict crop yields under various climate scenarios.',
     'Keywords': 'climate change, agriculture, environmental science'},
    
    {'Library': 'Scopus', 'Global_ID': 'W5', 'Local_ID': '5', 
     'Title': 'Machine Learning in Financial Portfolio Management', 
     'Abstract': 'We propose a novel deep learning approach for stock market prediction. Our model achieves 85% accuracy on historical data, demonstrating the potential of AI in financial applications.',
     'Keywords': 'machine learning, finance, portfolio management'},
    
    # Cases that fail EC2 (published before 2015)
    {'Library': 'IEEE', 'Global_ID': 'W6', 'Local_ID': '6', 
     'Title': 'Software Testing Best Practices in 2010', 
     'Abstract': 'This paper presents testing methodologies for software quality assurance. Published in 2010, it discusses unit testing, integration testing, and test-driven development. We analyze data from 30 companies.',
     'Keywords': 'software testing, quality assurance, 2010'},
    
    {'Library': 'Scopus', 'Global_ID': 'W7', 'Local_ID': '7', 
     'Title': 'Scrum Methodology in Software Projects 2012', 
     'Abstract': 'We analyze the adoption of Scrum methodology in software development projects during 2012. Survey results from 30 companies show widespread use of agile practices. The study examines productivity metrics.',
     'Keywords': 'scrum, agile, project management, 2012'},
    
    # Cases that fail EC3 (abstract too short) - should have abstracts < 50 chars
    {'Library': 'Springer', 'Global_ID': 'W8', 'Local_ID': '8', 
     'Title': 'Code Review Practices', 
     'Abstract': 'This paper discusses code review. We explore best practices.',
     'Keywords': 'code review'},
    
    {'Library': 'IEEE', 'Global_ID': 'W9', 'Local_ID': '9', 
     'Title': 'DevOps Implementation', 
     'Abstract': 'We explore DevOps. The methodology section is brief.',
     'Keywords': 'devops'},
    
    # Duplicate case (same Global_ID - EC4)
    {'Library': 'IEEE', 'Global_ID': 'W1', 'Local_ID': '10', 
     'Title': 'Software Engineering Hiring Practices in Tech Companies', 
     'Abstract': 'This study examines hiring practices in software engineering companies through a systematic survey. We analyze recruitment channels, interview processes, and hiring criteria. The findings include statistical analysis.',
     'Keywords': 'software engineering, hiring, recruitment'},
    
    # Cases that pass EC but fail IC
    {'Library': 'Scopus', 'Global_ID': 'W10', 'Local_ID': '11', 
     'Title': 'Recruitment Challenges in IT Industry', 
     'Abstract': 'This research examines the challenges faced by IT companies in recruiting qualified candidates. Through interviews with HR managers and analysis of job postings, we identify key pain points in the hiring process. The findings are descriptive but lack empirical validation.',
     'Keywords': 'recruitment, IT, hiring challenges'},
    
    # Cases that pass both EC and IC
    {'Library': 'Springer', 'Global_ID': 'W11', 'Local_ID': '12', 
     'Title': 'Technical Interview Processes', 
     'Abstract': 'We analyze technical interview processes at major software companies. The study includes data from 100 companies and discusses the effectiveness of various assessment methods. We present quantitative findings on candidate performance. Limitations include selection bias in the sample.',
     'Keywords': 'interview, technical assessment, hiring'},
    
    {'Library': 'IEEE', 'Global_ID': 'W12', 'Local_ID': '13', 
     'Title': 'Job Market Analysis for Software Developers', 
     'Abstract': 'This paper presents an analysis of the software developer job market. We examine salary trends, demand patterns, and skill requirements across different regions using data from multiple job boards. The methodology includes web scraping and statistical analysis. Results provide insights for career planning.',
     'Keywords': 'job market, software developers, salary'},
    
    # More normal cases
    {'Library': 'Scopus', 'Global_ID': 'W13', 'Local_ID': '14', 
     'Title': 'Hiring Pipeline Optimization with Machine Learning', 
     'Abstract': 'We propose a machine learning approach to optimize hiring pipelines. By analyzing historical hiring data from 10,000 candidates, our model identifies optimal candidate screening criteria. The system achieves 90% accuracy in predicting successful hires. We discuss implementation challenges and future work.',
     'Keywords': 'hiring pipeline, ML, optimization'},
    
    {'Library': 'Springer', 'Global_ID': 'W14', 'Local_ID': '15', 
     'Title': 'Onboarding Practices in Software Companies', 
     'Abstract': 'This study examines onboarding practices and their impact on employee retention. Survey data from 50 companies reveals best practices for new developer integration. We analyze correlation between onboarding duration and employee satisfaction scores. The research includes limitations section.',
     'Keywords': 'onboarding, employee retention, software companies'},
    
    {'Library': 'IEEE', 'Global_ID': 'W15', 'Local_ID': '16', 
     'Title': 'Software Engineering Salary Survey 2023', 
     'Abstract': 'We present a comprehensive salary survey for software engineers across different experience levels and geographic regions. Data from 1000 respondents provides market insights. The methodology includes statistical analysis of compensation patterns. Findings discuss regional variations and in-demand skills.',
     'Keywords': 'salary, survey, software engineering'},
    
    # Additional edge cases
    {'Library': 'Scopus', 'Global_ID': 'W16', 'Local_ID': '17', 
     'Title': 'Cultural Fit Assessment in Software Hiring', 
     'Abstract': 'This paper investigates the role of cultural fit assessment in software company hiring. We analyze various assessment methods and their correlation with employee performance. The study uses data from performance reviews and exit interviews. Results show mixed findings on predictive validity.',
     'Keywords': 'cultural fit, hiring, assessment'},
    
    {'Library': 'Springer', 'Global_ID': 'W17', 'Local_ID': '18', 
     'Title': 'Remote Hiring Practices Post-Pandemic', 
     'Abstract': 'We examine how hiring practices have changed in the post-pandemic era for software companies. The study focuses on remote interview techniques and their effectiveness compared to in-person processes. Data from 200 hiring managers provides insights. We discuss limitations of self-reported data.',
     'Keywords': 'remote hiring, pandemic, interview'},
    
    {'Library': 'IEEE', 'Global_ID': 'W18', 'Local_ID': '19', 
     'Title': 'Technical Skills Assessment Tools Comparison', 
     'Abstract': 'This paper reviews and compares various technical skills assessment tools used in software hiring. We evaluate coding challenges, portfolio reviews, and practical assignments based on validity and reliability metrics. The study includes data from 50 companies. Findings provide recommendations for assessment design.',
     'Keywords': 'assessment tools, technical skills, hiring'},
    
    {'Library': 'Scopus', 'Global_ID': 'W19', 'Local_ID': '20', 
     'Title': 'Candidate Experience Impact on Offer Acceptance', 
     'Abstract': 'We investigate candidate experience during the hiring process and its impact on offer acceptance rates. Survey data from 500 candidates provides insights into candidate expectations and satisfaction. The methodology includes regression analysis. Results indicate communication frequency matters more than process length.',
     'Keywords': 'candidate experience, hiring process'},
    
    {'Library': 'Springer', 'Global_ID': 'W20', 'Local_ID': '21', 
     'Title': 'Diversity Metrics in Software Engineering Teams', 
     'Abstract': 'This study analyzes diversity metrics in software engineering teams and their correlation with team performance. Data from 200 teams across 50 companies is presented. We examine gender, age, and educational background diversity. Findings show diverse teams have higher innovation metrics but not necessarily better delivery performance.',
     'Keywords': 'diversity, software teams, team performance'},
]

wl_df = pd.DataFrame(wl_data)

# Create GL test data (no abstracts - test SKIPPED policy)
gl_data = [
    {'#': 1, 'Posicao': '1', 'Title': 'Tech Company Hiring Guide 2024', 
     'URL': 'https://example.com/hiring-guide', 'Source_File': 'google_results_1.txt'},
    {'#': 2, 'Posicao': '2', 'Title': 'Software Engineer Job Description Example', 
     'URL': 'https://example.com/job-desc', 'Source_File': 'google_results_1.txt'},
    {'#': 3, 'Posicao': '3', 'Title': 'Why We Hire Remote Developers', 
     'URL': 'https://example.com/remote-hiring', 'Source_File': 'google_results_1.txt'},
    {'#': 4, 'Posicao': '4', 'Title': 'Interview Process at FAANG Companies', 
     'URL': 'https://example.com/faang-interview', 'Source_File': 'google_results_1.txt'},
    {'#': 5, 'Posicao': '5', 'Title': 'Salary Negotiation Tips for Developers', 
     'URL': 'https://example.com/salary-tips', 'Source_File': 'google_results_1.txt'},
    {'#': 6, 'Posicao': '1', 'Title': 'Best Hiring Practices for Startups', 
     'URL': 'https://example.com/startup-hiring', 'Source_File': 'google_results_2.txt'},
    {'#': 7, 'Posicao': '2', 'Title': 'Technical Interview Preparation Guide', 
     'URL': 'https://example.com/interview-prep', 'Source_File': 'google_results_2.txt'},
    {'#': 8, 'Posicao': '3', 'Title': 'Candidate Assessment Framework', 
     'URL': 'https://example.com/assessment', 'Source_File': 'google_results_2.txt'},
    {'#': 9, 'Posicao': '4', 'Title': 'Onboarding Checklist for New Hires', 
     'URL': 'https://example.com/onboarding', 'Source_File': 'google_results_2.txt'},
    {'#': 10, 'Posicao': '5', 'Title': 'Remote Work Policy Examples', 
     'URL': 'https://example.com/remote-policy', 'Source_File': 'google_results_2.txt'},
]

gl_df = pd.DataFrame(gl_data)

# Save to Excel
with pd.ExcelWriter('tests/atlas_sample_input.xlsx', engine='openpyxl') as writer:
    wl_df.to_excel(writer, sheet_name='White Literature', index=False)
    gl_df.to_excel(writer, sheet_name='Grey Literature', index=False)

print('Created: tests/atlas_sample_input.xlsx')
print(f'WL: {len(wl_df)} rows')
print(f'GL: {len(gl_df)} rows')