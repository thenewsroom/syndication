# Create your views here.
import datetime
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib.humanize.templatetags.humanize import intcomma
from django.db.models import Sum
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import render_to_response
from django.template.context import RequestContext

from reportlab.pdfgen import canvas
from reportlab.platypus import Spacer, SimpleDocTemplate, Table, TableStyle, Paragraph, flowables
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4

from accounts.models import Account
from cutils.utils import ContifyDateUtil
from royalties.models import Payable, Receivable, Royalty
import xlwt, operator, itertools, collections
from cms.models import Entry
from django.db.models import Count
from calendar import monthrange
from decimal import Decimal
from datetime import timedelta


@login_required
def receivable_detail(request, id):
    """
    get the details for the receivable - for internal use only
    """
    receivable = get_object_or_404(Receivable, id=id)
    payables = Payable.objects.user_payables(request.user).filter(receivable=receivable).select_related()

    return render_to_response('royalties/receivable_detail.html',
                              {'object': receivable, 'payables': payables, },
                              context_instance=RequestContext(request))


@login_required
def royalty_by_customer_widget(request):
    """
    royalty statements to be displayed on the dashboard
    """
    royalties = Royalty.objects.all()
    if not request.user.is_superuser:
        try:
            royalties = royalties
        except:
            raise Http404

    # restrict it to past one year only
    s, e = ContifyDateUtil().year()
    if request.user.id == 247:
        s = s - timedelta(days=730)
        u = User.objects.get(id=247)
        royalties = Royalty.objects.user_royalties(user=u). \
            filter(statement_date__range=(s, e), deliver=True
                   ).order_by('-statement_date')
    else:
        royalties = Royalty.objects.user_royalties(request.user). \
            filter(statement_date__range=(s, e), deliver=True
                   ).order_by('-statement_date')

    return render_to_response('royalties/royalty_account_widget.html',
                              {'royalties': royalties, },
                              context_instance=RequestContext(request))


@login_required
def royalty_by_account(request, slug, year, month):
    """
    get the royalty statements for a particular account for a given month
    """
    account = get_object_or_404(Account, slug=slug)

    statement_date = datetime.datetime.strptime('%s-%s' % (year, month), '%Y-%b')
    s, e = ContifyDateUtil(statement_date).month()

    royalties = Royalty.objects.user_royalties(request.user).filter(
        account=account, statement_date__range=(s, e), deliver=True
    ).order_by('-statement_date')

    return render_to_response('royalties/royalty_account_list.html',
                              {'object': account, 'royalties': royalties, },
                              context_instance=RequestContext(request))


@login_required
def royalty_statement_detail(request, id):
    """
    get the details for a particular royalty statement
    link will be shared with the customers
    """
    royalty = get_object_or_404(
        Royalty.objects.user_royalties(request.user), id=id)
    payables = royalty.get_payables(request.user)
    # create a dict to map payable's exchange rate
    payableMapDict = {}
    for p in payables:
        payableMapDict[p.id] = p.get_exchange_rate()

    payableResults = payables.values('id', 'publication__title',
                                     'receivable__received_from__title',
                                     'receivable__title', 'receivable__received_on',
                                     'receivable__currency', 'revenue',
                                     'revenue_share', 'payable', 'tds_rate'
                                     ).order_by('receivable__received_from__title', 'receivable__title'
                                                )
    # lets add exchange rate in payableResults
    for item in payableResults:
        item['get_exchange_rate'] = payableMapDict[item['id']]

    groupByResults = []
    # lets prepare a list to group payableResults by receivable__received_from and
    # receivable__title
    for key, items in itertools.groupby(payableResults, operator.itemgetter(
            'receivable__received_from__title', 'receivable__title')):
        groupByResults.append(list(items))

    # lets prepare a list with calculated data
    payableDataDict = {}
    payableDataDict['dataList'] = []
    payableDataDict['calculatedData'] = {}
    results = []
    netPayableAmount = 0
    netTdsAmount = 0
    for payable_group in groupByResults:
        dataDict = collections.defaultdict(unicode)
        dataDict['dataList'] = []
        dataDict['dataList'].extend(payable_group)
        dataDict['calculatedData'] = {}
        accountPayable = 0
        for payable in payable_group:
            accountPayable += payable['payable']
        dataDict['calculatedData']['accountPayable'] = "%.2f" % accountPayable
        tdsAmount = accountPayable * payable_group[0]['tds_rate'] / 100
        dataDict['calculatedData']['tdsAmount'] = "%.2f" % tdsAmount
        netPayable = accountPayable - tdsAmount
        dataDict['calculatedData']['netPayable'] = "%.2f" % netPayable
        netPayableAmount += netPayable
        netTdsAmount += tdsAmount
        results.append(dataDict)

    payableDataDict['dataList'].extend(results)
    payableDataDict['calculatedData']['netPayableAmount'] = "%.2f" % netPayableAmount
    payableDataDict['calculatedData']['netTdsAmount'] = "%.2f" % netTdsAmount

    return render_to_response('royalties/royalty_detail.html',
                              {'object': royalty, 'payableDataDict': payableDataDict, 'display_one_column': 'Y'},
                              context_instance=RequestContext(request))


@login_required
def royalty_statement_print(request, id):
    """
    same as royalty statement detail, will output a PDF instead of html
    """
    royalty = get_object_or_404(Royalty, id=id)
    # get the list of payables
    payables = royalty.get_payables(request.user)

    # let us prepare the pdf, set the mime type, filename
    response = HttpResponse(mimetype='application/pdf')
    filename = 'Royalty_Statement_%s_%s_%05d.pdf' % (
        royalty.account.slug, royalty.statement_date.strftime('%b-%Y'), int(id))
    response['Content-Disposition'] = 'attachment; filename=%s' % (filename)

    # we use reportlab to generate the pdf, we will use SimpleDocTemplate and
    # keep adding elements to it
    doc = SimpleDocTemplate(response)  # basic container for the file
    elements = []  # container for the objects
    styles = getSampleStyleSheet()  # get the sample styles
    width, height = A4  # default size is A4

    # start adding elements in the following order:
    # the title: Athena Information Solutions Pvt. Ltd.
    # the royalty title
    # the royalty statement line level details and the adjustment (as a table)
    # Notes, if any
    # statement sent to and royalty details

    elements.append(Paragraph(
        "Athena Information Solutions Pvt Ltd", styles['Title']))
    elements.append(flowables.HRFlowable(width=width, spaceAfter=0.4 * inch, color=colors.black))
    elements.append(Paragraph(royalty.__unicode__(), styles['Heading1']))
    elements.append(Paragraph("Please find below your statement showing the royalties due to you for the period shown",
                              styles['Heading3']))

    # for pdf - data needs to be list of lists - let us extract details from payables
    data = []
    data.append(['Publication', 'Client', 'For period', 'Received On',
                 'Revenue', 'Exchange', 'Royalty', 'Royalty Due'])
    for i in payables:
        data.append([
            i.publication, i.receivable.received_from,
            i.receivable.title, i.receivable.received_on.strftime('%b %d, %Y'),
            '%s %s' % (i.receivable.currency, intcomma(i.revenue)),
            i.get_exchange_rate(),
            '%d%s' % (i.revenue_share, u' %'), 'Rs %s' % intcomma(i.payable)]
        )

    # add the adjustments etc to the same data list
    extra_text = ""
    if royalty.notes:
        extra_text = " (see notes below)"
    data.append(['Amount to be paid', '', '', '', '', '', '', 'Rs %s' % (intcomma(royalty.revenue))])
    data.append(['Adjustment%s' % (extra_text), '', '', '', '', '', '', 'Rs %s' % (intcomma(royalty.adjustment))])
    data.append(['Amount Payable', '', '', '', '', '', '', 'Rs %s' % (intcomma(royalty.amount_payable()))])

    line_items_table = Table(data)
    line_len = len(data)
    line_items_table.setStyle(TableStyle([
        # header row - keep it in bold
        ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
        ('LINEABOVE', (0, 0), (-1, 0), 1, colors.black),
        ('LINEBELOW', (0, 0), (-1, 0), 1, colors.black),
        ('FONT', (0, 0), (-1, 0), 'Times-Bold'),

        # make all numerical fields right aligned, exclude header row
        ('ALIGN', (4, 1), (-1, -1), 'RIGHT'),

        # draw the grid
        ('INNERGRID', (0, 0), (-1, line_len - 4), 0.25, colors.gray),
        ('BACKGROUND', (0, 0), (8, 0), colors.lavender),

        # make sure the last 3 rows span all the columns
        ('SPAN', (0, line_len - 3), (-2, line_len - 3)),
        ('SPAN', (0, line_len - 2), (-2, line_len - 2)),
        ('SPAN', (0, line_len - 1), (-2, line_len - 1)),

        # keep the Amount to be paid and Amount payable in bold
        ('FONT', (0, -3), (-1, -3), 'Times-Bold'),
        ('LINEABOVE', (0, -3), (-1, -3), 1, colors.black),
        ('FONT', (0, -1), (-1, -1), 'Times-Bold'),
        ('LINEABOVE', (0, -1), (-1, -1), 1, colors.black),
        ('LINEBELOW', (0, -1), (-1, -1), 1, colors.black),
    ]))

    # add table to the doc
    elements.append(line_items_table)
    elements.append(Spacer(0, 0.1 * inch))

    # add the notes - if they exist
    if royalty.notes:
        elements.append(Paragraph("Notes: ", styles['Heading2']))
        elements.append(Paragraph(royalty.notes, styles['Normal']))
        elements.append(Spacer(0, 0.1 * inch))

    # add the sent to details
    elements.append(Paragraph("Statement sent to: ", styles['Heading2']))
    elements.append(Paragraph(royalty.get_sent_to(), styles['Normal']))
    elements.append(Paragraph(royalty.get_sent_to_street_address(), styles['Normal']))
    elements.append(Paragraph(royalty.get_sent_to_city_state(), styles['Normal']))
    elements.append(Paragraph(royalty.get_sent_to_country(), styles['Normal']))
    elements.append(Paragraph(royalty.get_sent_to_email(), styles['Normal']))
    elements.append(Spacer(0, 0.1 * inch))

    # add royalty department details
    elements.append(Paragraph("For any queries, contact: ", styles['Heading2']))
    elements.append(Paragraph("Account Department", styles['Normal']))
    elements.append(Paragraph("accounts@contify.com", styles['Normal']))
    elements.append(Paragraph("011-4057-6200 / 5200", styles['Normal']))

    # all done - let us build the doc and finish!
    doc.build(elements)
    return response


def financialReport(request):
    """
    """
    # import pdb
    # pdb.set_trace()
    d = datetime.datetime.now()
    start_date = datetime.datetime.strptime(request.GET['start'], "%Y-%m-%d")
    end_date = datetime.datetime.strptime(request.GET['end'], "%Y-%m-%d")
    if not (start_date and end_date):
        end_date = d
        start_date = (d - datetime.timedelta(days=180)).replace(hour=0, minute=0, second=0, microsecond=0)

    p = Payable.objects.all().select_related()
    if start_date and end_date:
        p = p.filter(receivable__duration_start__gte=start_date.date(), receivable__duration_end__lte=end_date.date())

    pub_list = list(p.values_list('publication__id', flat=True).distinct())

    payable_results = p.values("publication__id", "account__title", "publication__title",
                               'revenue', "receivable__received_from__title",
                               "receivable__duration_start", "receivable__duration_end",
                               )

    result_list = []
    for p_item in payable_results:
        if not (p_item['receivable__duration_end'].month - p_item['receivable__duration_start'].month) == 2:
            result_list.append(p_item)
        else:
            n = 0
            r = Decimal("%.3f" % (float(p_item['revenue']) / 3.00))
            while n < 3:
                sd = p_item['receivable__duration_start']
                sd = sd.replace(month=(sd.month + n))
                ed = sd.replace(day=monthrange(sd.year, sd.month)[1])
                n = n + 1
                result_list.append({'publication__title': p_item['publication__title'],
                                    'receivable__duration_start': sd,
                                    'account__title': p_item['account__title'],
                                    'revenue': r, 'publication__id': p_item['publication__id'],
                                    'receivable__duration_end': ed,
                                    'receivable__received_from__title': p_item['receivable__received_from__title']})

    # result_list = list(payable_results)
    result_list.sort(key=operator.itemgetter('publication__id'))
    item_list = []
    for key, items in itertools.groupby(result_list, operator.itemgetter('publication__id')):
        item_list.append(list(items))

    eqs = Entry.objects.select_related("publication").only("publication", "status").filter(
        created_on__gte=start_date, created_on__lte=end_date, status=2,
        updated_on__gte=start_date, updated_on__lte=end_date,
        publication__id__in=pub_list)

    final_report_list = []
    for ilist in item_list:
        dt_list = list(
            set([(ditem['receivable__duration_start'], ditem['receivable__duration_end']) for ditem in ilist]))
        c = 0
        while c < len(dt_list):
            if dt_list[c]:
                new_d = {}
                new_d['buyers'] = []
                for ditem in ilist:
                    if ditem['receivable__duration_start'] == dt_list[c][0] and ditem['receivable__duration_end'] == \
                            dt_list[c][1]:
                        new_d['publication__id'] = ditem['publication__id']
                        new_d['publication__title'] = ditem['publication__title']
                        new_d['account__title'] = ditem['account__title']
                        new_d['receivable__duration_start'] = ditem['receivable__duration_start']
                        new_d['receivable__duration_end'] = ditem['receivable__duration_end']
                        new_d['buyers'].append((ditem['receivable__received_from__title'], ditem['revenue']))
                final_report_list.append(new_d)
            c = c + 1

    buyers = ('Acquiremedia', 'Bloomberg Finance L.P.', 'Factiva', 'Gale Cengage',
              'LexisNexis', 'Mobile XL', 'ProQuest', 'Thomson Reuters', 'Yahoo',
              'Yahoo Finance', 'Yahoo Finance Contify Bnaking')

    # lets initialize sheet clolumns
    wbk = xlwt.Workbook()
    sheet = wbk.add_sheet('sheet 1')
    row = 0
    column = 0
    sheet.write(row, column, 'Month')
    sheet.write(row, column + 1, "Publication Account")
    sheet.write(row, column + 2, "Publication Title")
    col = 3
    for b_name in buyers:
        ############################################################
        ###     now there are 10 valid buyers                    ###
        ###     column no. for each buyer:                       ###
        ###     {"Acquiremedia": "column+3",                     ###
        ###      "Bloomberg Finance L.P." = "column+4",          ###
        ###     "Factiva":"column+5",                            ###
        ###     "Gale Cengage":"column+6",                       ###
        ###     "LexisNexis":"column+7",                         ###
        ###     "Mobile XL":"column+8",                          ###
        ###     "ProQuest":"column+9",                           ###
        ###     "Thomson Reuters":"column+10",                   ###
        ###     "Yahoo":"column+11",                             ###
        ###     "Yahoo Finance":"column+12",                     ###
        ###     "Yahoo Finance Contify Bnaking":"column+13",}    ###
        ############################################################
        sheet.write(row, column + col, "%s Revenue" % (b_name))
        col = col + 1
    sheet.write(row, column + 14, "Total Doc")
    sheet.write(row, column + 15, "Total Revenue")
    sheet.write(row, column + 16, "Revenue Per Doc")

    for report_dict in final_report_list:
        from datetime import time
        msd = datetime.datetime.combine(
            report_dict['receivable__duration_start'], time())
        med = datetime.datetime.combine(
            report_dict['receivable__duration_end'], time().replace(hour=23, minute=59))
        month_name = report_dict['receivable__duration_start'].strftime("%d-%m-%Y")
        account = report_dict['account__title']
        publication = report_dict['publication__title']
        pub_id = report_dict['publication__id']
        entry_count = eqs.filter(publication__id=pub_id,
                                 updated_on__gte=msd,
                                 updated_on__lte=med
                                 ).count()
        # buyers and revenue
        revenue_per_buyer = report_dict['buyers']
        acquiremedia_revenue = ''
        bloomberg_revenue = ''
        factiva_revenue = ''
        gale_revenue = ''
        ln_revenue = ''
        mx_revenue = ''
        pq_revenue = ''
        tr_revenue = ''
        yahoo_revenue = ''
        yf_revenue = ''
        yfcb_revenue = ''
        total_revenue = 0.0
        for b, r in revenue_per_buyer:
            if b == "Acquiremedia":
                acquiremedia_revenue = str(r)
                if acquiremedia_revenue:
                    total_revenue = total_revenue + float(r)

            if b == "Bloomberg Finance L.P.":
                bloomberg_revenue = str(r)
                if bloomberg_revenue:
                    total_revenue = total_revenue + float(r)

            if b == "Factiva":
                factiva_revenue = str(r)
                if factiva_revenue:
                    total_revenue = total_revenue + float(r)

            if b == "Gale Cengage":
                gale_revenue = str(r)
                if gale_revenue:
                    total_revenue = total_revenue + float(r)
            if b == "LexisNexis":
                ln_revenue = str(r)
                if ln_revenue:
                    total_revenue = total_revenue + float(r)

            if b == "Mobile XL":
                mx_revenue = str(r)
                if mx_revenue:
                    total_revenue = total_revenue + float(r)

            if b == "ProQuest":
                pq_revenue = str(r)
                if pq_revenue:
                    total_revenue = total_revenue + float(r)

            if b == "Thomson Reuters":
                tr_revenue = str(r)
                if tr_revenue:
                    total_revenue = total_revenue + float(r)

            if b == "Yahoo":
                yahoo_revenue = str(r)
                if yahoo_revenue:
                    total_revenue = total_revenue + float(r)

            if b == "Yahoo Finance":
                yf_revenue = str(r)
                if yf_revenue:
                    total_revenue = total_revenue + float(r)

            if b == "Yahoo Finance Contify Bnaking":
                yfcb_revenue = str(r)
                if yfcb_revenue:
                    total_revenue = total_revenue + float(r)

        # lets write data in xls file
        row = row + 1
        sheet.write(row, column, month_name)
        sheet.write(row, column + 1, account)
        sheet.write(row, column + 2, publication)
        ##sheet.write(row, column+3, acquiremedia_revenue)
        ##sheet.write(row, column+4, bloomberg_revenue)
        ##sheet.write(row, column+5, factiva_revenue)
        ##sheet.write(row, column+6, gale_revenue)
        ##sheet.write(row, column+7, ln_revenue)
        ##sheet.write(row, column+8, mx_revenue)
        ##sheet.write(row, column+9, pq_revenue)
        ##sheet.write(row, column+10, tr_revenue)
        ##sheet.write(row, column+11, yahoo_revenue)
        ##sheet.write(row, column+12, yf_revenue)
        ##sheet.write(row, column+13, yfcb_revenue)
        try:
            sheet.write(row, column + 3, float(acquiremedia_revenue))
        except:
            sheet.write(row, column + 3, acquiremedia_revenue)

        try:
            sheet.write(row, column + 4, float(bloomberg_revenue))
        except:
            sheet.write(row, column + 4, bloomberg_revenue)

        try:
            sheet.write(row, column + 5, float(factiva_revenue))
        except:
            sheet.write(row, column + 5, factiva_revenue)

        try:
            sheet.write(row, column + 6, float(gale_revenue))
        except:
            sheet.write(row, column + 6, gale_revenue)

        try:
            sheet.write(row, column + 7, float(ln_revenue))
        except:
            sheet.write(row, column + 7, ln_revenue)

        try:
            sheet.write(row, column + 8, float(mx_revenue))
        except:
            sheet.write(row, column + 8, mx_revenue)

        try:
            sheet.write(row, column + 9, float(pq_revenue))
        except:
            sheet.write(row, column + 9, pq_revenue)

        try:
            sheet.write(row, column + 10, float(tr_revenue))
        except:
            sheet.write(row, column + 10, tr_revenue)

        try:
            sheet.write(row, column + 11, float(yahoo_revenue))
        except:
            sheet.write(row, column + 11, yahoo_revenue)

        try:
            sheet.write(row, column + 12, float(yf_revenue))
        except:
            sheet.write(row, column + 12, yf_revenue)

        try:
            sheet.write(row, column + 13, float(yfcb_revenue))
        except:
            sheet.write(row, column + 13, yfcb_revenue)

        total_doc = entry_count
        try:
            sheet.write(row, column + 14, float(total_doc))
        except:
            sheet.write(row, column + 14, str(total_doc))
        try:
            sheet.write(row, column + 15, float(total_revenue))
        except:
            sheet.write(row, column + 15, str(total_revenue))

        if total_doc and total_revenue:
            revenue_per_doc = float(total_revenue) / float(total_doc)
            revenue_per_doc = "%.3f" % (revenue_per_doc)
        else:
            revenue_per_doc = ''
        try:
            sheet.write(row, column + 16, float(revenue_per_doc))
        except:
            sheet.write(row, column + 16, revenue_per_doc)

    response = HttpResponse(mimetype='application/vnd.ms-excel; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename=FinancialReport_%s.xls' % (d.strftime("%Y%m%d%H%M%S"))
    wbk.save(response)
    response['Content-Disposition'] = 'attachment; filename=FinancialReport_%s.xls' % (d.strftime("%Y%m%d%H%M%S"))
    return response

