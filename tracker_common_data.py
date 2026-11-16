"""Static data lifted from the original trackers: base SQL, Excel header layout, holidays."""

BASE_SQL = """SELECT CONCAT(eud1.user_first_name, ' ', eud1.user_last_name) AS 'CAT Name',CONCAT(eud2.user_first_name, ' ', eud2.user_last_name) AS 'CAT TL Name',CONCAT(eud4.user_first_name, ' ', eud4.user_last_name) AS 'DM',IF(ecm.dqc_released_date IS NULL,'PVT',IF(ecc.client_id IN (116118,136168,128652,116116,111656,124146),'NBGV',IF(ecc.client_id IN (78475,104790,110774,111654,115012,118466,119105,119106,119107,135775,137057,138322,138889,142093,145572,147531,147552,147616,147932,148005,148239,148690,148893,148952,149138,149140,149159,149491,149649,150496,150510,153575,153886,154083,154677,154895,154975,155952,156000,157825,158686,158692,158918,158964,159421,160444,160783,160798,160804,161391,161393,162249,162395,162408,162435,162436,162877,162999,163026,163066,163224,163602,163904,163906,163987,164337,164446,164815,164913,164979,165025,165478,165486,165491,165724,166814,167145,167341,167355,167867,167870,168054,168481,168577,168643,169017,169333,169438,170092,170186,170485,170539,170555,170610,170765,170769,171444,172035,172398,172570,172571,172578,172580,172692,172727,172989,173003,173010) AND ecc.check_id IN (83,144),'Education Verification W', CHECK_OPS_NAME))) AS 'Department',ecc.Case_Check_id AS 'Case Check Id',Company_name AS 'Company Name',CONCAT(IFNULL(first_name,''),' ',IFNULL(Middle_name,''),' ',IFNULL(last_name,'')) AS 'Candidate Name',Process_name AS 'Process Name',office_name AS 'Location', case_ars_no AS 'Case Ars No', received_date AS 'Case Received Date',ecm.created_date AS 'Case Created Date',IF(ecc.client_id IN (82164,183941) AND ecc.check_id IN (44,45,47,56,63,67,72,76,99,132,133,137,138,143),DATE_ADD(received_date, INTERVAL 4 DAY),IF(ecm.client_id IN (82164,183941),DATE_ADD(case_expected_closure_date, INTERVAL 14 DAY),case_expected_closure_date)) AS 'Case Due Date', (CASE case_status
            WHEN '1' THEN 'New (Incomplete)'
            WHEN '2' THEN 'On Hold'
            WHEN '3' THEN 'Insufficient'
            WHEN '4' THEN 'Work in Progress'
            WHEN '5' THEN 'Pending for report'
            WHEN '6' THEN 'Closed by Client'
            WHEN '7' THEN 'Completed'
            WHEN '8' THEN 'Closed by Authbridge' 
            WHEN '9' THEN 'Closed-Case Insufficient'
            WHEN '10' THEN 'HighlighterCase'
            WHEN '11' THEN 'SignOff Pending' 
            WHEN '12' THEN 'Pending For Duplicity' 
            WHEN '13' THEN 'Duplicity' 
            WHEN '14' THEN 'Scrap' 
            WHEN '15' THEN 'Excel Pending For Duplicity' 
            WHEN '16' THEN 'Escalation Raised' 
            WHEN '17' THEN 'Escalation Received' 
            WHEN '18' THEN 'Excel Duplicity' END) AS 'Case Status',ecc.check_name AS 'Check Name',check_created_on AS 'Check Created On',go_ahead_date AS 'Go Ahead Date',check_expected_closure AS 'Check Expected Closure',ecc.priority_flag AS 'Priority Flag',insuff_date AS 'Insuff Date',insuff_fulfill_date AS 'Insuff Fulfill Date',CONCAT(eud.user_first_name, ' ', eud.user_last_name) AS 'Verifier Name', queue_name AS 'Queue Name',(CASE check_status
            WHEN '0' THEN 'Documentation Pending'
            WHEN '1' THEN 'New/UnAssigned'
            WHEN '2' THEN 'On Hold'
            WHEN '3' THEN 'Insufficient'
            WHEN '4' THEN 'Work in Progress'
            WHEN '5' THEN 'Awaiting Response'
            WHEN '6' THEN 'Escalated'
            WHEN '7' THEN 'In Research'
            WHEN '8' THEN 'Completed'
            WHEN '9' THEN 'Disabled'
            WHEN '10' THEN 'case closed by client'
            WHEN '11' THEN 'Closed with Insufficiency'
            WHEN '12' THEN 'Closed-case Insufficient'
            WHEN '13' THEN 'Contractually on Hold'END) AS 'Check Status 1',CONCAT(eud3.user_first_name, ' ', eud3.user_last_name) AS 'Escalated To Whom',REPLACE(ecc.insuff_remarks,'\r\n','') AS 'Insuff Remarks',assigned_date AS 'Assigned Date',interim_report_due AS 'Interim Report Due',(CASE INTERIM_REPORT_REQ 
            WHEN '0' THEN 'Not Applicable'
            WHEN '1' THEN 'Applicable' END) AS 'Interim Status',check_closure_date AS 'Check Closure Date',IF(check_status IN (2,3,4,5,6,7,13) AND DATE(check_closure_date) IS NOT NULL,
            (CASE check_status
            WHEN '0' THEN 'Documentation Pending-Reopen Check'
            WHEN '1' THEN 'New/UnAssigned-Reopen Check'
            WHEN '2' THEN 'On Hold-Reopen Check'
            WHEN '3' THEN 'Insufficient-Reopen Check'
            WHEN '4' THEN 'Work in Progress-Reopen Check'
            WHEN '5' THEN 'Awaiting Response-Reopen Check'
            WHEN '6' THEN 'Escalated-Reopen Check'
            WHEN '7' THEN 'In Research-Reopen Check'
            WHEN '8' THEN 'Completed-Reopen Check'
            WHEN '9' THEN 'Disabled-Reopen Check'
            WHEN '10' THEN 'case closed by client-Reopen Check'
            WHEN '11' THEN 'Closed with Insufficiency-Reopen Check'
            WHEN '12' THEN 'Closed-case Insufficient-Reopen Check'
            WHEN '13' THEN 'Contractually on Hold-Reopen Check'END),
            (CASE check_status
            WHEN '0' THEN 'Documentation Pending'
            WHEN '1' THEN 'New/UnAssigned'
            WHEN '2' THEN 'On Hold'
            WHEN '3' THEN 'Insufficient'
            WHEN '4' THEN 'Work in Progress'
            WHEN '5' THEN 'Awaiting Response'
            WHEN '6' THEN 'Escalated'
            WHEN '7' THEN 'In Research'
            WHEN '8' THEN 'Completed'
            WHEN '9' THEN 'Disabled'
            WHEN '10' THEN 'case closed by client'
            WHEN '11' THEN 'Closed with Insufficiency'
            WHEN '12' THEN 'Closed-case Insufficient'
            WHEN '13' THEN 'Contractually on Hold'END)) AS 'Check Reopen Status',DQC_DONE_TIME AS 'Check QC Done Date', IF(ecc.family_id=5,(SELECT company_name FROM ec_master_company emc1 WHERE eccvs.org_id=emc1.company_id), IF(ecc.family_id=4,(SELECT IF(emei1.institute_name IS NULL,emei.institute_name,CONCAT(emei1.institute_name,' - ',emei.institute_name)) FROM ec_master_educational_institute emei 
            LEFT JOIN ec_master_educational_institute emei1 ON emei.UNIVERSITY_ID=emei1.institute_id WHERE eccvs.org_id=emei.institute_id),(SELECT city_name FROM ec_master_city emc2 WHERE eccvs.org_id=emc2.city_id)))AS 'Verification Source',(SELECT COUNT(*)  FROM ec_case_checks ecc5 WHERE ecm.case_id=ecc5.case_id AND check_status NOT IN (8,9,10,11,12) HAVING COUNT(*)=1) AS 'Overall One Check Pending',IF((case_expected_closure_date=CURRENT_DATE),'Today TAT',IF(DATEDIFF(case_expected_closure_date,CURRENT_DATE)=1,'1 Day to TAT',IF(case_expected_closure_date>=CURRENT_DATE,'In TAT','Out of TAT')))AS 'Case TAT',IF((check_expected_closure=CURRENT_DATE),'Today TAT',IF(DATEDIFF(check_expected_closure,CURRENT_DATE)=1,'1 Day to TAT',IF(check_expected_closure>=CURRENT_DATE,'In TAT','Out of TAT'))) AS 'Check Level TAT',IF(ecc.family_id=5,(SELECT CONCAT(city_name,' - ',state_name) FROM ec_master_company emc1 
            LEFT JOIN ec_master_city emc5 ON emc1.city_id=emc5.city_id
            LEFT JOIN ec_master_state ems ON emc5.state_id=ems.state_id
            WHERE eccvs.org_id=emc1.company_id),
            IF(ecc.family_id=4,
            (SELECT CONCAT(city_name,' - ',state_name) FROM ec_master_educational_institute emei
            LEFT JOIN ec_master_city emc5 ON emei.city_id=emc5.city_id
            LEFT JOIN ec_master_state ems ON emc5.state_id=ems.state_id
            WHERE eccvs.org_id=emei.institute_id),
            (SELECT CONCAT(city_name,' - ',state_name) FROM ec_master_city emc2 
            LEFT JOIN ec_master_state ems ON emc2.state_id=ems.state_id
            WHERE eccvs.org_id=emc2.city_id))) AS 'Verification Source City State',ec.client_external_id AS 'Client External Code',(SELECT report_sent_on FROM ec_case_reports ecr WHERE ecr.case_id=ecm.case_id AND report_type=0 AND report_status=5 ORDER BY ecr.case_report_id DESC LIMIT 1) AS 'Intrim Sent Date',IF(INTERIM_REPORT_REQ=0,'Not Applicable',CONCAT((CASE INTERIM_REPORT_REQ
                WHEN 0 THEN 'Not Applicable'
                WHEN 1 THEN 'Interim Applicable' END),(SELECT IF(report_sent_on IS NULL,' But Not Sent',' Sent') FROM ec_case_reports ecr WHERE ecr.case_id=ecm.case_id AND report_type=0 AND report_status=5 ORDER BY ecr.case_report_id DESC LIMIT 1))) AS 'Interim Status 1',IF(ecm.client_id IN (78230),'Candidate calling-process specific',IF( ecm.client_id IN (78406,78347,77952,78475,75778,79055,77941,78212,76299,76357,78362,75723,75762,78226,82164,78583,79061,78342,78302,78249,83576,78478,75750,78517,94712),'Candidate calling','')) AS 'Candidate Calling',(SELECT IF(vendor_request_status IN (2,13,15),'',agent_name) FROM ec_vendor_requests evr LEFT JOIN ec_master_verification_agents emva ON evr.vendor_id=emva.agent_id WHERE ecc.case_check_id=evr.case_check_id ORDER BY vendor_request_id DESC LIMIT 1) AS 'Vendor Name','' AS City,''AS 'Institute Name',ecc.CHECK_LAST_UPDATED AS 'Last Touch',(SELECT created FROM  ec_billing_info ebf WHERE ecc.case_check_id=ebf.case_check_id ORDER BY id DESC LIMIT 1) AS 'Max Reopen Date',TAT_DAYS_TYPE AS 'Process TAT Type',' ' AS 'Check Wise Ageing','' AS 'Check Wise Ageing Slab', DQC_DONE_TIME AS 'DQC Done Time',GREATEST(IFNULL(DATE(check_created_on),0),IFNULL(go_ahead_date,0),IFNULL(insuff_fulfill_date,0), IFNULL(DATE(DQC_DONE_TIME),0),IFNULL((SELECT created FROM  ec_billing_info ebf WHERE ecc.case_check_id=ebf.case_check_id ORDER BY id DESC LIMIT 1),0)) AS 'Max 1',GREATEST(IFNULL(go_ahead_date,0),IFNULL(insuff_fulfill_date,0),IFNULL((SELECT DATE(created) FROM  ec_billing_info ebf WHERE ecc.case_check_id=ebf.case_check_id ORDER BY id DESC LIMIT 1),0),IFNULL(received_date,0)) AS 'Max',(SELECT REWORK_DATE FROM ec_case_rework_details ecrd WHERE  ecc.case_check_id=ecrd.case_check_id AND ecrd.CASE_REPORT_ID IS NOT NULL ORDER BY ID DESC LIMIT 1) AS 'Rework Date','' AS 'Ageing (Rework)',' ' AS 'Ageing Slab (Rework)',REPLACE((SELECT REWORK_COMMENT FROM ec_case_rework_details ecrd WHERE  ecc.case_check_id=ecrd.case_check_id AND ecrd.CASE_REPORT_ID IS NOT NULL ORDER BY ID DESC LIMIT 1),'\r\n','') AS 'Rework Comment',(CASE ecm.data_source
                    WHEN '1' THEN 'Mcs'
                    WHEN '2' THEN 'Bridge'
                    WHEN '3' THEN 'Case'
                    WHEN '4' THEN 'CandidateApp'
                    WHEN '5' THEN 'Api'
                    WHEN '6' THEN 'ExcelCase'
                    WHEN '7' THEN 'SingleCase'
                    WHEN '9' THEN 'Mail'
                    WHEN '10' THEN 'Link'
                    WHEN '11' THEN 'HardCopy' 
                    WHEN '12' THEN 'ClientPortal' 
                    WHEN '13' THEN 'DATA ENTRY - NON PVT' 
                    WHEN '14' THEN 'iBridge' 
                    WHEN '15' THEN 'PVT Microservices' 
                    WHEN '16' THEN 'RuleEngine' 
                    WHEN '17' THEN 'RuleEngine-API' 
                    WHEN '18' THEN 'RuleEngine-iBridge'
                    WHEN '19' THEN 'IBridge Manual' 
                    WHEN '20' THEN 'IBridge Quick Flow' 
                    WHEN '21' THEN 'RuleEngine - IBridge Manual'
                    WHEN '22' THEN 'RuleEngine - IBridge Quick Flow' END) AS 'Case Data Source',
                (SELECT CONCAT(user_first_name, ' ', user_last_name) FROM ec_user_details WHERE ecc.documented_by=user_id) AS 'Check Created By',(SELECT approve_date FROM ec_vendor_requests WHERE case_check_id=ecc.case_check_id ORDER BY vendor_request_id DESC LIMIT 1 ) AS 'Vendor Assigned Date',(SELECT REQUEST_DATE FROM ec_research_requests err WHERE ecc.case_check_id=err.case_check_id ORDER BY RESEARCH_REQUEST_ID DESC LIMIT 1) AS 'Research Raised Date',ecm.dqc_released_date AS 'DQC Released Date',(CASE CASE_LEVEL
            WHEN 0 THEN 'Not Sure'
            WHEN 1 THEN 'Not Senior'
            WHEN 2 THEN 'Senior' END) AS 'Seniority Level',(SELECT ESCALATION_RESPONDED_ON FROM ec_check_verifier_escalation ecve WHERE ecc.case_check_id=ecve.case_check_id AND ecve.ESCALATION_RESPONDED_ON IS NOT NULL ORDER BY id DESC LIMIT 1 ) AS 'Escalation Responded', IF(client_category IN (1,5),'Not to be Share in Insuff tracker','Can be share in Insuff Tracker') AS 'Insuff Client Status',IFNULL(NULLIF(INTERIM_REPORT_TAT, 0), 'No TAT') AS 'Interim TAT',etwtir.insuff_rule AS 'Insuff Rule',etwtir.onhold_rule AS 'Onhold Rule' FROM ec_case_checks ecc
            INNER JOIN ec_case_master ecm ON (ecm.case_id = ecc.case_id)
            LEFT JOIN ec_checks ecs ON (ecs.check_id = ecc.check_id)
            LEFT JOIN ec_client ec ON ec.client_id = ecc.client_id
            LEFT JOIN ec_user_details eud ON eud.user_id = ecc.check_verifier
            LEFT JOIN ec_user_details eud1 ON ec.cat_id=eud1.user_id
            LEFT JOIN ec_user_details eud2 ON ec.cat_tl=eud2.user_id
            LEFT JOIN ec_user_details eud3 ON ecc.check_assigned_to=eud3.user_id
            LEFT JOIN ec_user_details eud4 ON ec.cat_account_manager=eud4.user_id
            LEFT JOIN ec_master_company emc ON emc.company_id = ecc.client_id
            LEFT JOIN ec_case_candidates ecc1 ON ecc1.candidate_id=ecc.candidate_id
            LEFT JOIN ec_client_process ecp ON ecm.process_id=ecp.process_id
            LEFT JOIN ec_master_company_locations emcl ON ecm.client_office_id=emcl.office_id
            LEFT JOIN ec_check_queues ecq ON ecc.check_queue=ecq.queue_id
            LEFT JOIN ec_case_check_verification_source eccvs ON ecc.case_check_id=eccvs.case_check_id
            LEFT JOIN ec_total_wip_tracker_insuff_rule etwtir ON etwtir.client_id = ecc.client_id
            WHERE ecc.case_id=ecm.case_id AND case_status NOT IN (1,5,6,7,8,14) AND check_status IN ({status})
            AND IFNULL(first_name,'') NOT LIKE '%dummy%' AND IFNULL(first_name,'') NOT LIKE '%Test%' AND IFNULL(middle_name,'') NOT LIKE '%Test%' AND IFNULL(last_name,'') NOT LIKE '%Test%'
            and ecc.check_id<>193
            AND company_id NOT IN (1000,88031,140093,151588,157843,180562,228135,260883,263464,263586,263588,263590,263591,263106,280435,272202,263464,263586,263588,263590,263591,267032,415975,370640,231747,398807,357512)"""

HEADERS = ['CAT Name', 'CAT TL Name', 'DM', 'Department', 'Case Check Id', 'Company Name', 'Candidate Name', 'Process Name', 'Location', 'Case Ars No', 'Case Received Date', 'Case Created Date', 'Ageing (Initiation)', 'Ageing (Initiation) Bucket', 'Case Due Date', 'Case Status', 'Check Name', 'Check Created On', 'Go Ahead Date', 'Check Expected Closure', 'Priority Flag', 'Insuff Date', 'Insuff Fulfill Date', 'Verifier Name', 'Queue Name', 'Check Status 1', 'Escalated To Whom', 'Insuff Remarks', 'Assigned Date', 'Interim Report Due', 'Interim Status', 'Check Closure Date', 'Check Reopen Status', 'Check QC Done Date', 'Verification Source', 'Overall One Check Pending', 'Case TAT', 'Check Level TAT', 'Verification Source City State', 'Client External Code', 'Intrim Sent Date', 'Interim Status 1', 'Candidate Calling', 'Vendor Name', 'City', 'Institute Name', 'Last Touch', 'Max Reopen Date', 'Process TAT Type', 'Check Wise Ageing', 'Check Wise Ageing Slab', 'DQC Done Time', 'Max', 'Rework Date', 'Ageing (Rework)', 'Ageing Slab (Rework)', 'Rework Comment', 'Case Data Source', 'Check Created By', 'Vendor Assigned Date', 'Research Raised Date', 'DQC Released Date', 'Seniority Level', 'Escalation Responded', 'Insuff Client Status', 'Max 1', 'OT Ageing', 'OT Bucket', 'Insuff To Be Closed', 'Ageing', 'Bucket', 'Insuff Ageing', 'Insuff Bucket', 'Interim TAT', 'Interim Due Date', 'Interim TAT Due', 'UAN Number', 'Month', 'Insuff Closure Status', 'Insuff Rule', 'Onhold Rule', '1', '3', '4', 'CS Bucket - Insuff', 'CS Bucket - Onhold']

HOLIDAYS = ['2006-03-15', '2006-04-14', '2006-08-09', '2006-08-15', '2006-10-02', '2006-10-19', '2006-10-23', '2006-12-25', '2007-01-01', '2007-01-26', '2007-03-04', '2007-04-06', '2007-08-15', '2007-08-28', '2007-10-02', '2007-10-21', '2007-11-09', '2007-12-25', '2008-01-01', '2008-01-26', '2008-03-21', '2008-03-22', '2008-08-15', '2008-10-02', '2008-10-09', '2008-10-28', '2008-12-25', '2009-01-01', '2009-01-26', '2009-03-11', '2009-04-10', '2009-08-05', '2009-08-15', '2009-09-28', '2009-10-02', '2009-10-13', '2009-10-17', '2009-12-25', '2010-01-01', '2010-01-26', '2010-03-01', '2010-04-02', '2010-07-06', '2010-08-15', '2010-08-24', '2010-10-02', '2010-10-17', '2010-11-05', '2010-12-25', '2011-01-01', '2011-01-26', '2011-03-20', '2011-04-22', '2011-05-17', '2011-08-13', '2011-08-15', '2011-10-02', '2011-10-06', '2011-10-26', '2011-10-27', '2011-12-25', '2012-01-26', '2012-02-11', '2012-02-20', '2012-03-08', '2012-03-10', '2012-03-24', '2012-04-06', '2012-04-14', '2012-05-12', '2012-06-09', '2012-08-02', '2012-08-15', '2012-10-02', '2012-10-24', '2012-11-13', '2012-12-25', '2013-01-01', '2013-01-26', '2013-03-27', '2013-08-15', '2013-08-20', '2013-10-02', '2013-10-14', '2013-11-03', '2013-12-25', '2014-01-01', '2014-01-26', '2014-03-17', '2014-04-10', '2014-08-15', '2014-10-02', '2014-10-03', '2014-10-15', '2014-10-23', '2014-10-24', '2014-12-25', '2015-01-01', '2015-01-26', '2015-03-06', '2015-04-03', '2015-08-15', '2015-10-02', '2015-10-22', '2015-11-11', '2015-12-25', '2016-01-01', '2016-01-26', '2016-03-24', '2016-03-25', '2016-08-15', '2016-08-18', '2016-10-02', '2016-10-11', '2016-10-30', '2016-10-31', '2016-12-25', '2017-01-01', '2017-01-26', '2017-03-13', '2017-08-07', '2017-08-15', '2017-09-30', '2017-10-02', '2017-10-19', '2017-10-20', '2017-12-25', '2018-01-01', '2018-01-26', '2018-03-02', '2018-08-15', '2018-10-02', '2018-10-19', '2018-11-07', '2018-12-25', '2019-01-01', '2019-01-26', '2019-03-21', '2019-04-19', '2019-08-15', '2019-10-02', '2019-10-08', '2019-10-27', '2019-10-28', '2019-12-25', '2020-01-01', '2020-01-26', '2020-03-10', '2020-04-10', '2020-05-25', '2020-08-15', '2020-08-03', '2020-10-02', '2020-10-25', '2020-11-14', '2020-11-16', '2020-12-25', '2021-01-01', '2021-01-26', '2021-03-29', '2021-04-02', '2021-07-21', '2021-08-15', '2021-08-22', '2021-10-02', '2021-10-15', '2021-11-04', '2021-11-05', '2021-12-25', '2022-01-01', '2022-01-26', '2022-03-18', '2022-04-15', '2022-05-03', '2022-08-15', '2022-10-02', '2022-10-05', '2022-10-24', '2022-10-25', '2022-12-25', '2023-01-26', '2023-03-08', '2023-08-30', '2023-08-15', '2023-10-02', '2023-10-24', '2023-11-13', '2023-12-25', '2024-01-01', '2024-01-26', '2024-03-25', '2024-08-15', '2024-08-19', '2024-10-02', '2024-11-01', '2024-12-25', '2024-10-31', '2025-01-01', '2025-01-26', '2025-03-14', '2025-08-15', '2025-10-02', '2025-10-20', '2025-10-21', '2025-12-25', '2026-01-01', '2026-01-26', '2026-03-04', '2026-08-15', '2026-08-28', '2026-10-02', '2026-10-20', '2026-11-09', '2026-11-10', '2026-12-25']
