"""HSE indicator catalogue. Company-defined measures must be reviewed before use."""
GROUPS = {
'Incidents & injuries': '''Work-related fatalities|Fatal injury frequency rate|Serious injury and fatality cases|High-potential incidents|Total recordable injury and illness cases|TRIR / TCIR|TRIFR|Lost-time injury cases|LTIFR|DART rate|Days-away-from-work cases|Restricted-work / job-transfer cases|Medical-treatment cases|First-aid cases|Injury severity rate|Total workdays lost|Total restricted-duty days|Average days lost per lost-time case|Occupational illness cases|Occupational illness incidence rate|Property-damage incidents|Fire and explosion incidents|Electrical incidents|Dropped-object incidents|Repeat incidents''',
'Hazards & participation': '''Hazards reported|Hazard-reporting rate|Near misses reported|Near-miss reporting frequency|Workers participating in hazard reporting|Safety observations completed|Actionable-report percentage|Positive safety practices observed|Unsafe conditions identified|At-risk behaviours observed|Stop-work interventions|Stop-work concerns resolved before restart|Average response time to reported concerns|Reporters receiving feedback|Employee safety suggestions implemented|Safety committee participation|Safety culture survey score|Worker confidence in reporting without retaliation''',
'Risk & critical controls': '''Activities covered by current risk assessments|Risk assessments reviewed on time|JSA / JHA completion|Pre-task briefings completed|Workforce participation in risk assessments|High-risk activities with approved controls|Critical-control verifications completed|Critical controls verified as effective|Critical-control failures identified|Time to restore failed critical controls|Open high-risk findings|Overdue high-risk actions|Risk-control implementation completion|Control effectiveness checks completed|Management of Change assessments completed before implementation|Unauthorised or unassessed changes|Pre-startup safety review completion''',
'Inspections & actions': '''Planned workplace inspections completed|Planned HSE audits completed|Inspection conformity percentage|Audit conformity percentage|Major nonconformities|Minor nonconformities|Repeat findings|Corrective-action closure percentage|Corrective actions closed on time|Open overdue actions|Average corrective-action closure time|Actions verified as effective|Actions reopened|Incident investigations completed on time|Investigation quality review pass rate|Investigation recommendations implemented|Lessons learned communicated|Lessons learned verified as implemented''',
'Training & competence': '''HSE induction completion|Mandatory training completion|Refresher training completed on time|Training participant-hours|Training hours per worker|Toolbox talks delivered against plan|Toolbox-talk attendance|Training assessment pass rate|Practical competency assessment pass rate|Roles filled by competent authorised personnel|Valid competency certificates|Expired mandatory certifications|Training effectiveness verified in the workplace|Supervisor HSE competency coverage|Emergency-response competency coverage''',
'Leadership & management': '''Leadership safety visits completed|Leadership-visit actions closed on time|HSE management reviews completed|Management-review actions closed|HSE objectives achieved|HSE improvement plan completion|Safety committee meetings held against plan|Safety committee actions closed|Management response time to escalated HSE issues|Required HSE roles filled|HSE programme funding delivered against approved needs|Employee participation in HSE improvement activities''',
'Permits & high-risk work': '''Permit-to-work audit compliance|Jobs requiring permits with valid permits|Permit handover and close-out compliance|Isolation / lockout-tagout compliance|Zero-energy verification compliance|Confined-space entry compliance|Required atmospheric tests completed|Confined-space rescue readiness|Work-at-height control compliance|Fall-protection equipment inspection compliance|Scaffold inspection and tagging compliance|Lifting-plan compliance|Lifting equipment certification compliance|Lifting accessory inspection compliance|Hot-work control compliance|Excavation permit and protection compliance|Underground-service clearance compliance|Simultaneous-operations control compliance|Line-breaking compliance|Electrical work authorisation compliance''',
'Equipment & integrity': '''Safety-critical preventive maintenance completed on time|Overdue safety-critical maintenance|Safety-critical equipment availability|Safety-device functional test completion|Safety-device test failure rate|Machine guarding compliance|Emergency-stop test compliance|Defective equipment removed from service on time|Average repair time for safety-critical defects|Statutory equipment examinations completed on time|Portable electrical equipment inspection compliance|Pressure-system inspection compliance|Alarm and interlock bypass duration|Unauthorised safety-system bypasses|Safety-critical equipment failures''',
'Occupational health': '''Required health surveillance completed|Occupational health referrals completed on time|Work-related sickness absence rate|Occupational health recommendations implemented|Return-to-work plans reviewed|Exposure-monitoring plan completion|Exposure measurements above applicable limits|Workers with assessed exposure above limits|Noise-control compliance|Vibration-control compliance|Respiratory protection programme compliance|Required respirator fit testing completed|Local exhaust ventilation examination compliance|Chemical exposure-control compliance|Safety Data Sheet availability and currency|Chemical labelling and storage compliance|Ergonomic assessments completed|Ergonomic improvements implemented|Work-related musculoskeletal disorder cases|Heat-related illness cases|Heat-stress control compliance|Drinking-water and welfare inspection compliance|Fatigue-management compliance|Psychosocial risk assessments completed|Psychosocial risk-control actions completed''',
'Emergency & fire': '''Emergency drills completed against plan|Emergency drill participation|Alarm-to-evacuation completion time|Personnel accountability completion time|Emergency response mobilisation time|Drill performance objectives achieved|Drill corrective actions closed|Emergency equipment inspection compliance|Fire alarm and detection test compliance|Fire suppression system availability|Fire extinguisher inspection compliance|Emergency exit and access-route compliance|First-aider coverage against requirements|Emergency responder coverage against requirements|Rescue equipment readiness|Emergency plan review completion''',
'Contractors & suppliers': '''Contractor HSE prequalification completion|Contractor induction completion|Contractor competency verification|Contractor risk assessment approval|Contractor inspection compliance|Contractor audit completion|Contractor corrective-action closure|Contractor critical-control compliance|Contractor incident reporting timeliness|Contractor TRIR|Contractor high-potential incidents|Contractor HSE performance review completion|Supplier HSE compliance''',
'Transport & driving': '''Vehicle collisions|Preventable vehicle collisions|Collision rate per million kilometres|Road-traffic fatalities and injuries|Vehicle pre-use inspection completion|Vehicle maintenance completed on time|Driver authorisation and licence compliance|Seat-belt compliance|Speeding events per distance driven|Harsh-driving events per distance driven|Driving-hours and rest-period compliance|Journey-management compliance|Distracted-driving events|Reversing-control compliance|Pedestrian-vehicle segregation compliance|Load-securing compliance''',
'Process safety': '''Tier 1 process safety events|Tier 2 process safety events|Process safety event rate|Loss-of-primary-containment events|Quantity of hazardous material released|Operating-limit excursions|Safety instrumented system demands|Emergency shutdown demands|Safety-critical proof tests completed on time|Safety-critical proof-test failures|Overdue process hazard analysis actions|Process operating procedure review completion|Operator process-safety competency coverage|Mechanical integrity inspection completion|Temporary repairs exceeding approved duration|Impaired process safety barriers''',
'Environment': '''Environmental incidents|Reportable environmental incidents|Spills and leaks|Spill volume|Spill response time|Environmental complaints|Environmental complaints resolved on time|Environmental permit exceedances|Environmental monitoring completed against plan|Total waste generated|Hazardous waste generated|Waste intensity per unit of output|Waste recycling percentage|Waste diversion percentage|Waste segregation compliance|Waste documentation compliance|Total water withdrawal|Total water consumption|Water intensity per unit of output|Water reused or recycled|Wastewater discharge volume|Wastewater discharge-limit compliance|Total energy consumption|Energy intensity per unit of output|Renewable energy share|Fuel consumption|Scope 1 greenhouse gas emissions|Scope 2 greenhouse gas emissions|Scope 3 greenhouse gas emissions|Greenhouse gas emissions intensity|Emissions reduction against baseline|Air pollutant emissions|Dust monitoring exceedances|Boundary noise exceedances|Environmental restoration commitments completed''',
'Compliance & costs': '''Compliance obligations evaluated on time|Verified legal compliance percentage|Regulatory notices and citations|Regulatory fines and penalties|Required permits and licences valid|Mandatory reports submitted on time|Statutory records complete and current|HSE document reviews completed on time|HSE data completeness|HSE reporting timeliness|HSE data error rate|Direct incident costs|Estimated indirect incident costs|Cost per incident|Workers compensation claim costs|Incident-related downtime|Property-damage costs|Environmental remediation costs|Verified savings from HSE improvements'''
}
# Explicit definitions for the daily workflow; other catalogue entries remain draft
# until the organisation sets its own measurement rule.
DAILY = {
'HSE induction completion': ('New starters inducted','New starters requiring induction'),
'Pre-task briefings completed': ('Crews briefed','Crews requiring briefing'),
'JSA / JHA completion': ('Tasks assessed','Tasks requiring assessment'),
'Permit-to-work audit compliance': ('Compliant permits checked','Permits checked'),
'Critical controls verified as effective': ('Effective critical controls checked','Critical controls checked'),
'Planned workplace inspections completed': ('Planned inspections completed','Inspections planned'),
'Heat-stress control compliance': ('Compliant checks','Checks completed'),
'Corrective actions closed on time': ('Actions due today closed on time','Actions due today'),
'Work-at-height control compliance': ('Compliant activities checked','Activities checked'),
'Waste segregation compliance': ('Compliant waste areas checked','Waste areas checked'),
'Confined-space entry compliance': ('Compliant entries checked','Entries checked'),
'Lifting-plan compliance': ('Compliant lifts checked','Lifts checked'),
'Excavation permit and protection compliance': ('Compliant excavations checked','Excavations checked'),
'Isolation / lockout-tagout compliance': ('Compliant isolations checked','Isolations checked'),
}
COUNTS_DAILY = {'Work-related fatalities','High-potential incidents','Total recordable injury and illness cases','Lost-time injury cases','First-aid cases','Hazards reported','Near misses reported','Stop-work interventions','Critical-control failures identified','Spills and leaks','Heat-related illness cases','Property-damage incidents','Total workdays lost'}
EXTRA = {
'Workforce on site': ('snapshot','workers','Workers present',''),
'Hours worked': ('sum','hours','Actual hours worked',''),
'PPE compliance': ('percentage','%','Compliant observations','Applicable observations'),
'Equipment pre-use check completion': ('percentage','%','Equipment checked','Equipment requiring checks'),
'Immediate hazard response': ('percentage','%','Serious hazards made safe before continuation','Serious hazards identified'),
'Housekeeping and access compliance': ('percentage','%','Compliant areas','Areas inspected'),
'Emergency readiness': ('percentage','%','Arrangements verified ready','Arrangements checked'),
'DART cases': ('sum','cases','Unique DART cases',''),
}
RATES = {
'TRIR / TCIR': ('Total recordable injury and illness cases','Hours worked',200000),
'LTIFR': ('Lost-time injury cases','Hours worked',1000000),
'DART rate': ('DART cases','Hours worked',200000),
'Injury severity rate': ('Total workdays lost','Hours worked',1000000),
}

def seed_catalog():
    items=[]
    for category,names in GROUPS.items():
        for name in names.split('|'):
            kind,unit,num,den='sum','count','Recorded count',''
            ready=False
            if name in DAILY:
                kind,unit='percentage','%'; num,den=DAILY[name]; ready=True
            elif name in COUNTS_DAILY:
                ready=True
            elif name == 'Overdue high-risk actions':
                kind,unit,num='snapshot','actions','Open overdue high-risk actions'; ready=True
            if name in RATES:
                kind,unit,ready='derived','rate',True
                num,den,_=RATES[name]
            items.append(dict(name=name,category=category,kind=kind,unit=unit,numerator_label=num,denominator_label=den,
                ready=int(ready),daily=int(name in DAILY or name in COUNTS_DAILY or name=='Overdue high-risk actions'),
                direction='higher' if kind=='percentage' else 'context',target=None,owner='',definition='Review case definitions, scope and measurement rules before activation.' if not ready else 'Enter actual shift data for the selected site. Percentages use matched numerator and denominator counts.'))
    for name,(kind,unit,num,den) in EXTRA.items():
        items.append(dict(name=name,category='Daily operations',kind=kind,unit=unit,numerator_label=num,denominator_label=den,ready=1,daily=1,direction='higher' if kind=='percentage' else 'context',target=None,owner='',definition='Record actual shift data. Missing values are not zero.'))
    return items
